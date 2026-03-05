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

  const rsResult = await db.execute({ sql: 'SELECT * FROM risk_scores WHERE analysis_id = ? ORDER BY score DESC', args: [params.analysisId] })
  const oppResult = await db.execute({ sql: 'SELECT * FROM opportunities WHERE analysis_id = ? ORDER BY sort_order', args: [params.analysisId] })
  const riskScores = rsResult.rows as any[]
  const opportunities = oppResult.rows as any[]

  const parsedOpp = opportunities.map((o: any) => ({
    ...o,
    implementation_steps: JSON.parse(o.implementation_steps || '[]'),
    related_services: JSON.parse(o.related_services || '[]'),
  }))

  let descParsed: any = {}
  try { descParsed = JSON.parse(analysis.description || '{}') } catch { }

  // Generate a simple HTML report for PDF
  const tierColors: Record<string, string> = {
    low: '#22C55E', moderate: '#F59E0B', high: '#F97316', critical: '#EF4444'
  }
  const tierColor = tierColors[analysis.risk_tier] || '#8B9AC4'

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>AI Risk Report — ${analysis.company_name}</title>
  <style>
    body { font-family: -apple-system, Inter, sans-serif; margin: 0; padding: 0; background: #060A12; color: #EEF2FF; }
    .page { max-width: 900px; margin: 0 auto; padding: 3rem 2rem; }
    .cover { min-height: 90vh; display: flex; flex-direction: column; justify-content: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 3rem; margin-bottom: 3rem;}
    h1 { font-size: 2.5rem; font-weight: 800; margin: 0 0 0.5rem; letter-spacing: -0.03em; }
    h2 { font-size: 1.25rem; font-weight: 700; margin: 2rem 0 1rem; color: #EEF2FF; }
    h3 { font-size: 1rem; font-weight: 600; margin: 1.5rem 0 0.5rem; }
    .badge { display: inline-block; padding: 0.3rem 0.9rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
    .score-box { display: inline-flex; align-items: center; justify-content: center; width: 90px; height: 90px; border-radius: 50%; border: 5px solid ${tierColor}; font-size: 2rem; font-weight: 800; color: ${tierColor}; margin-bottom: 1rem; }
    .risk-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }
    .bar { flex: 1; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 3px; }
    .opp-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
    .step { display: flex; gap: 0.75rem; margin-bottom: 0.5rem; align-items: flex-start; }
    .step-num { min-width: 24px; height: 24px; border-radius: 50%; background: rgba(59,123,246,0.15); color: #3B7BF6; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0; }
    .callouts { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin: 1rem 0; }
    .callout { padding: 0.875rem; border-radius: 6px; }
    .label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #8B9AC4; margin-bottom: 0.25rem; }
    .vendor-chip { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; background: rgba(139,154,196,0.1); border: 1px solid rgba(139,154,196,0.2); font-size: 0.75rem; color: #8B9AC4; margin: 0.2rem; text-decoration: none; }
    p { line-height: 1.7; margin: 0 0 0.75rem; color: #c4cde8; }
    .meta { color: #4D5B7F; font-size: 0.875rem; }
    @media print { body { background: white; color: #111; } }
  </style>
</head>
<body>
<div class="page">
  <!-- Cover -->
  <div class="cover">
    <div style="font-size:0.875rem;color:#3B7BF6;font-weight:600;margin-bottom:1rem;">PE SCAN · AI RISK REPORT</div>
    <h1>${analysis.company_name}</h1>
    ${analysis.company_url ? `<p class="meta">${analysis.company_url}</p>` : ''}
    ${analysis.industry ? `<p class="meta">${analysis.industry}</p>` : ''}
    <div style="margin-top:2rem;">
      <div class="score-box">${analysis.overall_risk_score?.toFixed(1)}</div>
      <div>
        <span class="badge" style="background:${tierColor}20;color:${tierColor};border:1px solid ${tierColor}40;">
          ${analysis.risk_tier?.toUpperCase()} RISK
        </span>
      </div>
    </div>
    ${descParsed.summary ? `<p style="margin-top:1.5rem;max-width:600px;">${descParsed.summary}</p>` : ''}
    <p class="meta" style="margin-top:2rem;">Generated ${new Date().toLocaleDateString()} · Powered by Claude AI</p>
  </div>

  <!-- Top Actions -->
  ${descParsed.topActions?.length ? `
  <h2>Top 3 Immediate Actions</h2>
  ${descParsed.topActions.map((a: string, i: number) => `
    <div class="step">
      <div class="step-num">${i + 1}</div>
      <p>${a}</p>
    </div>`).join('')}
  ` : ''}

  <!-- Risk Scores -->
  <h2>Risk Assessment</h2>
  ${riskScores.map((rs: any) => {
    const tc = ['low', 'moderate', 'high', 'critical']
    const sc = rs.score <= 3 ? '#22C55E' : rs.score <= 6 ? '#F59E0B' : rs.score <= 8 ? '#F97316' : '#EF4444'
    return `
    <div>
      <div class="risk-row">
        <div style="width:180px;font-size:0.875rem;font-weight:500;">${rs.category.replace(/_/g, ' ')}</div>
        <div class="bar"><div class="bar-fill" style="width:${(rs.score / 10) * 100}%;background:${sc};"></div></div>
        <div style="width:30px;font-weight:700;color:${sc};text-align:right;">${rs.score}</div>
      </div>
      ${rs.explanation ? `<p style="font-size:0.85rem;margin-left:196px;margin-top:-0.5rem;">${rs.explanation}</p>` : ''}
    </div>`
  }).join('')}

  <!-- Opportunities -->
  <h2 style="margin-top:3rem;">AI Opportunity Roadmap</h2>
  ${parsedOpp.map((opp: any) => `
  <div class="opp-card">
    <h3>${opp.title}</h3>
    <div style="margin-bottom:0.875rem;">
      <span class="badge" style="background:rgba(59,123,246,0.1);color:#3B7BF6;border:1px solid rgba(59,123,246,0.2);margin-right:0.5rem;">${opp.impact_rating} Impact</span>
      <span class="badge" style="background:rgba(139,154,196,0.08);color:#8B9AC4;border:1px solid rgba(139,154,196,0.15);">${opp.timeline}</span>
    </div>
    <p>${opp.description}</p>
    ${opp.implementation_steps?.length ? `
      <div style="margin-top:0.875rem;">
        ${opp.implementation_steps.map((s: string, i: number) => `<div class="step"><div class="step-num">${i + 1}</div><p style="margin:0;">${s}</p></div>`).join('')}
      </div>` : ''}
    <div class="callouts">
      <div class="callout" style="background:rgba(245,158,11,0.08);border-left:3px solid #F59E0B;">
        <div class="label">Investment</div>
        <div style="font-weight:700;color:#F59E0B;">${opp.investment_range}</div>
      </div>
      <div class="callout" style="background:rgba(34,197,94,0.08);border-left:3px solid #22C55E;">
        <div class="label">Potential ROI</div>
        <div style="font-weight:600;color:#22C55E;font-size:0.875rem;">${opp.roi_estimate}</div>
      </div>
    </div>
    ${opp.related_services?.length ? opp.related_services.map((svc: any) => `
      <div style="margin-top:0.75rem;">
        <div class="label">${svc.service_type}</div>
        ${(svc.vendors || []).map((v: any) => `<a href="${v.url}" class="vendor-chip">${v.name}</a>`).join('')}
      </div>`).join('') : ''}
  </div>`).join('')}
</div>
</body>
</html>`

  return new NextResponse(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    }
  })
}
