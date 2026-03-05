import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, initializeDb } from '@/lib/db/client'

export async function GET(
    req: NextRequest,
    { params }: { params: { analysisId: string } }
) {
    const session = await getServerSession(authOptions)
    if (!session?.user) return new NextResponse('Unauthorized', { status: 401 })

    await initializeDb()
    const db = getDb()
    const orgId = (session.user as any).orgId

    const analysisResult = await db.execute({
        sql: `SELECT ca.*, s.org_id FROM company_analyses ca JOIN scans s ON s.id = ca.scan_id WHERE ca.id = ? AND s.org_id = ?`,
        args: [params.analysisId, orgId],
    })
    const analysis = analysisResult.rows[0] as any
    if (!analysis) return new NextResponse('Not found', { status: 404 })

    const riskScoresResult = await db.execute({
        sql: `SELECT * FROM risk_scores WHERE analysis_id = ? ORDER BY score DESC`,
        args: [params.analysisId],
    })

    const opportunitiesResult = await db.execute({
        sql: `SELECT * FROM opportunities WHERE analysis_id = ? ORDER BY sort_order`,
        args: [params.analysisId],
    })

    // Parse description JSON (summary, topActions, shortDescription)
    let analysisSummary: string | null = null
    let topActions: string[] = []
    try {
        const desc = analysis.description ? JSON.parse(analysis.description as string) : {}
        if (typeof desc === 'object') {
            analysisSummary = desc.summary ?? desc.shortDescription ?? null
            topActions = Array.isArray(desc.topActions) ? desc.topActions : []
        }
    } catch {
        // description may be plain text from older records
        analysisSummary = typeof analysis.description === 'string' ? analysis.description : null
    }

    // Parse opportunity JSON fields for frontend
    const opportunities = (opportunitiesResult.rows as any[]).map((opp: any) => {
        let implementation_steps = opp.implementation_steps
        let related_services = opp.related_services
        try {
            if (typeof opp.implementation_steps === 'string') implementation_steps = JSON.parse(opp.implementation_steps)
        } catch { implementation_steps = [] }
        try {
            if (typeof opp.related_services === 'string') related_services = JSON.parse(opp.related_services)
        } catch { related_services = [] }
        return { ...opp, implementation_steps, related_services }
    })

    // Return shape expected by frontend (camelCase, flattened)
    return NextResponse.json({
        companyName: analysis.company_name ?? '',
        companyUrl: analysis.company_url ?? '',
        industry: analysis.industry ?? '',
        overallRiskScore: analysis.overall_risk_score != null ? Number(analysis.overall_risk_score) : null,
        riskTier: analysis.risk_tier ?? null,
        analysisSummary,
        topActions,
        riskScores: riskScoresResult.rows,
        opportunities,
    })
}

export async function DELETE(
    req: NextRequest,
    { params }: { params: { analysisId: string } }
) {
    const session = await getServerSession(authOptions)
    if (!session?.user) return new NextResponse('Unauthorized', { status: 401 })

    await initializeDb()
    const db = getDb()
    const orgId = (session.user as any).orgId

    // Verify ownership
    const analysisResult = await db.execute({
        sql: `SELECT ca.id, ca.scan_id FROM company_analyses ca JOIN scans s ON s.id = ca.scan_id WHERE ca.id = ? AND s.org_id = ?`,
        args: [params.analysisId, orgId],
    })
    if (analysisResult.rows.length === 0) {
        return new NextResponse('Not found', { status: 404 })
    }

    const scanId = (analysisResult.rows[0] as any).scan_id

    // Delete child records, then the analysis
    await db.execute({ sql: `DELETE FROM opportunities WHERE analysis_id = ?`, args: [params.analysisId] })
    await db.execute({ sql: `DELETE FROM risk_scores WHERE analysis_id = ?`, args: [params.analysisId] })
    await db.execute({ sql: `DELETE FROM company_analyses WHERE id = ?`, args: [params.analysisId] })

    // If the parent scan has no remaining analyses, delete it too
    const remaining = await db.execute({
        sql: `SELECT COUNT(*) as cnt FROM company_analyses WHERE scan_id = ?`,
        args: [scanId],
    })
    if (Number((remaining.rows[0] as any).cnt) === 0) {
        await db.execute({ sql: `DELETE FROM scans WHERE id = ?`, args: [scanId] })
    }

    return NextResponse.json({ ok: true })
}
