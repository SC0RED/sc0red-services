import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, generateId, initializeDb } from '@/lib/db/client'
import { discoverPortfolioCompanies } from '@/lib/scraper'
import { analyzeCompany } from '@/lib/ai/analyzeCompany'

// Allow up to 120 seconds for analysis (Vercel Pro) or 60s (Hobby)
export const maxDuration = 120

export async function POST(req: NextRequest) {
    try {
        const session = await getServerSession(authOptions)
        if (!session?.user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

        const { url, type } = await req.json()
        if (!url || !type) return NextResponse.json({ error: 'url and type required' }, { status: 400 })

        await initializeDb()
        const db = getDb()
        const scanId = generateId()

        let orgId = (session.user as any).orgId
        let userId = (session.user as any).id

        if (!orgId || !userId) {
            if (session.user?.email) {
                const u = await db.execute({ sql: `SELECT id, org_id FROM users WHERE email = ?`, args: [session.user.email] })
                if (u.rows[0]) {
                    userId = u.rows[0].id
                    orgId = u.rows[0].org_id
                } else {
                    return NextResponse.json({ error: 'User record not found in system' }, { status: 401 })
                }
            } else {
                return NextResponse.json({ error: 'Unauthorized: missing user email' }, { status: 401 })
            }
        }

        await db.execute({
            sql: `INSERT INTO scans (id, org_id, created_by, type, source_url, status, progress) VALUES (?, ?, ?, ?, ?, 'running', 0)`,
            args: [scanId, orgId, userId, type, url],
        })

        if (type === 'portfolio') {
            // Portfolio discovery: await inline, then return for user confirmation
            try {
                await db.execute({ sql: `UPDATE scans SET progress = 5 WHERE id = ?`, args: [scanId] })
                const companies = await discoverPortfolioCompanies(url)
                await db.execute({
                    sql: `UPDATE scans SET portfolio_companies = ?, status = 'awaiting_confirmation', progress = 20 WHERE id = ?`,
                    args: [JSON.stringify(companies), scanId],
                })
                return NextResponse.json({ scanId, status: 'awaiting_confirmation', portfolioCompanies: companies })
            } catch (err) {
                console.error(`Portfolio discovery failed for ${url}:`, err)
                await db.execute({ sql: `UPDATE scans SET status = 'failed' WHERE id = ?`, args: [scanId] })
                return NextResponse.json({
                    scanId,
                    error: `Portfolio discovery failed: ${err instanceof Error ? err.message : 'unknown error'}`
                }, { status: 500 })
            }
        }

        // Standalone company analysis: run inline (awaited) within this request
        const analysisId = generateId()
        await db.execute({
            sql: `INSERT INTO company_analyses (id, scan_id, company_name, company_url) VALUES (?, ?, '', ?)`,
            args: [analysisId, scanId, url],
        })

        try {
            await db.execute({ sql: `UPDATE scans SET progress = 10 WHERE id = ?`, args: [scanId] })

            const result = await analyzeCompany(url, async (_stage: string, pct: number) => {
                try {
                    await db.execute({ sql: `UPDATE scans SET progress = ? WHERE id = ?`, args: [Math.round(pct * 0.9), scanId] })
                } catch {
                    // Progress update is non-critical
                }
            })

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
                args: [JSON.stringify({ summary: result.riskAssessment.analysis_summary, topActions: result.opportunities.top_three_immediate_actions, shortDescription: result.profile.description }), analysisId],
            })

            await db.execute({
                sql: `UPDATE scans SET status = 'complete', progress = 100 WHERE id = ?`,
                args: [scanId],
            })

            return NextResponse.json({ scanId, status: 'complete', analysisId })
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Analysis failed'
            console.error(`Analysis failed for ${url}:`, errorMsg, err)
            await db.execute({
                sql: `UPDATE company_analyses SET error = ? WHERE id = ?`,
                args: [errorMsg, analysisId],
            })
            await db.execute({
                sql: `UPDATE scans SET status = 'failed', progress = 0 WHERE id = ?`,
                args: [scanId],
            })
            return NextResponse.json({ scanId, error: errorMsg }, { status: 500 })
        }
    } catch (error: any) {
        console.error('API Error in /api/scan/start:', error)
        return NextResponse.json({ error: error.message || 'Internal Server Error', stack: error.stack }, { status: 500 })
    }
}
