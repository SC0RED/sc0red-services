import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, generateId, initializeDb } from '@/lib/db/client'
import { analyzeCompany } from '@/lib/ai/analyzeCompany'

// Allow up to 300 seconds for portfolio analysis (multiple companies)
export const maxDuration = 300

export async function POST(
    req: NextRequest,
    { params }: { params: { scanId: string } }
) {
    const session = await getServerSession(authOptions)
    if (!session?.user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

    const { companies } = await req.json()
    if (!companies?.length) return NextResponse.json({ error: 'No companies provided' }, { status: 400 })

    await initializeDb()
    const db = getDb()
    const orgId = (session.user as any).orgId

    // Verify scan belongs to org
    const scanResult = await db.execute({
        sql: `SELECT * FROM scans WHERE id = ? AND org_id = ?`,
        args: [params.scanId, orgId],
    })
    if (!scanResult.rows.length) return NextResponse.json({ error: 'Scan not found' }, { status: 404 })

    await db.execute({
        sql: `UPDATE scans SET status = 'running', progress = 25 WHERE id = ?`,
        args: [params.scanId],
    })

    // Run portfolio analysis inline (awaited) — not fire-and-forget
    const total = companies.length
    const results: Array<{ name: string; status: string; analysisId?: string; error?: string }> = []

    // Create placeholder analyses for all companies upfront
    const analysisIds: string[] = []
    for (const company of companies) {
        const analysisId = generateId()
        analysisIds.push(analysisId)
        await db.execute({
            sql: `INSERT INTO company_analyses (id, scan_id, company_name, company_url) VALUES (?, ?, ?, ?)`,
            args: [analysisId, params.scanId, company.name, company.url],
        })
    }

    let completed = 0
    for (let idx = 0; idx < companies.length; idx++) {
        const company = companies[idx]
        const analysisId = analysisIds[idx]

        try {
            const result = await analyzeCompany(company.url)

            await db.execute({
                sql: `UPDATE company_analyses SET company_url = ?, company_name = ?, industry = ?, description = ?, overall_risk_score = ?, risk_tier = ?, analyzed_at = datetime('now') WHERE id = ?`,
                args: [result.actualUrl, result.profile.company_name, result.profile.industry, result.profile.description, result.riskAssessment.overall_score, result.riskAssessment.tier, analysisId],
            })

            for (const rs of result.riskAssessment.risk_scores) {
                await db.execute({
                    sql: `INSERT INTO risk_scores (id, analysis_id, category, score, explanation, evidence) VALUES (?, ?, ?, ?, ?, ?)`,
                    args: [generateId(), analysisId, rs.category, rs.score, rs.explanation, rs.evidence],
                })
            }

            for (let i = 0; i < result.opportunities.opportunities.length; i++) {
                const opp = result.opportunities.opportunities[i]
                await db.execute({
                    sql: `INSERT INTO opportunities (id, analysis_id, title, risk_mitigated, impact_rating, strategic_category, description, implementation_steps, timeline, investment_range, roi_estimate, related_services, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
                    args: [generateId(), analysisId, opp.title, opp.risk_mitigated, opp.impact_rating, opp.strategic_category, opp.description, JSON.stringify(opp.implementation_steps), opp.timeline, opp.investment_range, opp.roi_estimate, JSON.stringify(opp.related_services), i],
                })
            }

            await db.execute({
                sql: `UPDATE company_analyses SET description = ? WHERE id = ?`,
                args: [JSON.stringify({ summary: result.riskAssessment.analysis_summary, topActions: result.opportunities.top_three_immediate_actions }), analysisId],
            })

            results.push({ name: company.name, status: 'complete', analysisId })
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Analysis failed'
            console.error(`Analysis failed for ${company.name} (${company.url}):`, errorMsg)
            await db.execute({
                sql: `UPDATE company_analyses SET error = ? WHERE id = ?`,
                args: [errorMsg, analysisId],
            })
            results.push({ name: company.name, status: 'failed', error: errorMsg })
        }

        completed++
        const progress = Math.round(25 + (completed / total) * 70)
        try {
            await db.execute({
                sql: `UPDATE scans SET progress = ? WHERE id = ?`,
                args: [progress, params.scanId],
            })
        } catch {
            // Progress update is non-critical
        }
    }

    await db.execute({
        sql: `UPDATE scans SET status = 'complete', progress = 100 WHERE id = ?`,
        args: [params.scanId],
    })

    return NextResponse.json({ ok: true, results })
}
