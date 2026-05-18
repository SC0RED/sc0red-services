/**
 * S3 + DynamoDB persistence helpers for the async PDF export path.
 *
 * The Lambda runs out-of-band (boto3 ``InvocationType="Event"``) when
 * invoked by the Python API handler. After rendering the PDF, it:
 *   1. PUT the bytes to the per-analysis S3 key
 *   2. Conditional UpdateItem on the assessment record's PDF_EXPORT
 *      sub-row, transitioning ``status`` rendering → ready (or failed).
 *
 * The conditional UpdateItem GUARDS on the ``started_at`` timestamp that
 * the Lambda received in its input event. If the persisted ``started_at``
 * no longer matches — e.g., a parallel re-analyse cleared the field, or
 * a newer render was enqueued — the update fails and the Lambda exits
 * cleanly without overwriting the newer state. The orphan S3 object
 * (if any) is harmless: the next render of the same analysis overwrites
 * the same key.
 *
 * Module-level clients survive Lambda warm-restart, avoiding per-
 * invocation client init (~50 ms each).
 */

import { DynamoDBClient, UpdateItemCommand, ConditionalCheckFailedException } from '@aws-sdk/client-dynamodb'
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3'

let s3Client: S3Client | undefined
let ddbClient: DynamoDBClient | undefined

function getS3(): S3Client {
    if (!s3Client) s3Client = new S3Client({})
    return s3Client
}

function getDdb(): DynamoDBClient {
    if (!ddbClient) ddbClient = new DynamoDBClient({})
    return ddbClient
}

export interface UploadInput {
    bucket: string
    key: string
    bytes: Buffer
}

export async function uploadPdfToS3({ bucket, key, bytes }: UploadInput): Promise<void> {
    // The bucket policy enforces SSE-S3, so we don't need to set
    // ServerSideEncryption explicitly here. Content-Type lets browsers
    // following the presigned URL render the response as a PDF without
    // an extra content sniff.
    await getS3().send(
        new PutObjectCommand({
            Bucket: bucket,
            Key: key,
            Body: bytes,
            ContentType: 'application/pdf',
        }),
    )
}

export interface UpdateReadyInput {
    tableName: string
    analysisId: string
    s3Key: string
    inputStartedAt: string
    generatedAt: string
}

export type UpdateOutcome = { ok: true } | { ok: false; reason: 'conditional_failed' | 'unknown'; message?: string }

export async function markPdfExportReady({
    tableName,
    analysisId,
    s3Key,
    inputStartedAt,
    generatedAt,
}: UpdateReadyInput): Promise<UpdateOutcome> {
    return await runConditionalUpdate(tableName, analysisId, inputStartedAt, {
        UpdateExpression: 'SET #status = :ready, #s3_key = :s3_key, #generated_at = :generated_at',
        ExpressionAttributeNames: {
            '#status': 'status',
            '#s3_key': 's3_key',
            '#generated_at': 'generated_at',
            '#started_at': 'started_at',
        },
        ExpressionAttributeValues: {
            ':ready': { S: 'ready' },
            ':rendering': { S: 'rendering' },
            ':s3_key': { S: s3Key },
            ':generated_at': { S: generatedAt },
            ':input_started_at': { S: inputStartedAt },
        },
    })
}

export interface UpdateFailedInput {
    tableName: string
    analysisId: string
    inputStartedAt: string
    error: string
}

export async function markPdfExportFailed({
    tableName,
    analysisId,
    inputStartedAt,
    error,
}: UpdateFailedInput): Promise<UpdateOutcome> {
    // Truncate the error to 500 chars: DynamoDB attribute size limits
    // are generous (400KB per item) but render-failure messages can
    // be enormous (full Chromium stack traces). Truncation keeps the
    // record readable + bounded.
    const truncated = error.length > 500 ? error.slice(0, 497) + '...' : error
    return await runConditionalUpdate(tableName, analysisId, inputStartedAt, {
        UpdateExpression: 'SET #status = :failed, #error = :error',
        ExpressionAttributeNames: {
            '#status': 'status',
            '#error': 'error',
            '#started_at': 'started_at',
        },
        ExpressionAttributeValues: {
            ':failed': { S: 'failed' },
            ':rendering': { S: 'rendering' },
            ':error': { S: truncated },
            ':input_started_at': { S: inputStartedAt },
        },
    })
}

interface UpdateBody {
    UpdateExpression: string
    ExpressionAttributeNames: Record<string, string>
    ExpressionAttributeValues: Record<string, { S: string }>
}

async function runConditionalUpdate(
    tableName: string,
    analysisId: string,
    inputStartedAt: string,
    body: UpdateBody,
): Promise<UpdateOutcome> {
    try {
        await getDdb().send(
            new UpdateItemCommand({
                TableName: tableName,
                Key: {
                    pk: { S: `ASSESSMENT#${analysisId}` },
                    sk: { S: 'PDF_EXPORT' },
                },
                ConditionExpression:
                    '#status = :rendering AND #started_at = :input_started_at',
                ...body,
            }),
        )
        return { ok: true }
    } catch (error) {
        if (error instanceof ConditionalCheckFailedException) {
            return { ok: false, reason: 'conditional_failed' }
        }
        return {
            ok: false,
            reason: 'unknown',
            message: error instanceof Error ? error.message : 'unknown',
        }
    }
}
