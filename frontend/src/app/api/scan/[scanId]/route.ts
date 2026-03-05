import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, initializeDb } from '@/lib/db/client'

export async function GET(
    req: NextRequest,
    { params }: { params: { scanId: string } }
) {
    const session = await getServerSession(authOptions)
    if (!session?.user) return new NextResponse('Unauthorized', { status: 401 })

    await initializeDb()
    const db = getDb()
    const orgId = (session.user as any).orgId

    const scanResult = await db.execute({
        sql: `SELECT * FROM scans WHERE id = ? AND org_id = ?`,
        args: [params.scanId, orgId],
    })
    const scan = scanResult.rows[0] as any
    if (!scan) return new NextResponse('Not found', { status: 404 })

    const analysesResult = await db.execute({
        sql: `SELECT id, company_name, company_url, industry, overall_risk_score, risk_tier, analyzed_at, error FROM company_analyses WHERE scan_id = ?`,
        args: [params.scanId],
    })

    const portfolioCompanies = scan.portfolio_companies ? JSON.parse(scan.portfolio_companies as string) : []

    return NextResponse.json({
        status: scan.status,
        progress: scan.progress,
        type: scan.type,
        portfolioCompanies,
        analyses: analysesResult.rows,
    })
}
