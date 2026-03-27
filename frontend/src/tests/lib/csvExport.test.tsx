import { describe, it, expect, vi, beforeEach } from 'vitest'

import { exportAnalysisDetailCsv, exportAnalysesListCsv } from '@/lib/utils/csvExport'
import type { AnalysisData, AnalysisItem } from '@/lib/types/api'

let capturedContent: string
let capturedFilename: string

beforeEach(() => {
    capturedContent = ''
    capturedFilename = ''

    const OriginalBlob = globalThis.Blob
    vi.spyOn(globalThis, 'Blob').mockImplementation((parts?: BlobPart[], options?: BlobPropertyBag) => {
        capturedContent = (parts ?? []).join('')
        return new OriginalBlob(parts, options)
    })

    global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    global.URL.revokeObjectURL = vi.fn()

    const mockLink = { href: '', download: '', click: vi.fn() }
    Object.defineProperty(mockLink, 'download', {
        get: () => capturedFilename,
        set: (val: string) => {
            capturedFilename = val
        },
        configurable: true,
    })
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLElement)
})

function buildAnalysisData(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'a-1',
        companyName: 'Acme Corp',
        companyUrl: 'https://acme.com',
        industry: 'SaaS',
        overallRiskScore: 6.5,
        riskTier: 'high',
        riskScores: [
            { category: 'competitive_displacement', score: 8, rationale: 'Strong competition' },
            { category: 'technology_obsolescence', score: 5 },
        ],
        opportunities: [
            {
                title: 'Deploy AI Chatbot',
                description: 'Build a chatbot',
                impact_rating: 'High',
                timeline: 'Quick Win',
                strategic_category: 'Competitive Moat',
                value_lever: 'Revenue Side',
                investment_range: '$100K-$500K',
                roi_estimate: '30% improvement',
            },
        ],
        analyzedAt: '2026-03-01T00:00:00Z',
        ...overrides,
    }
}

describe('exportAnalysisDetailCsv', () => {
    it('creates a CSV blob and triggers download', () => {
        exportAnalysisDetailCsv(buildAnalysisData())
        expect(global.URL.createObjectURL).toHaveBeenCalled()
        expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
    })

    it('uses sanitized company name in filename', () => {
        exportAnalysisDetailCsv(buildAnalysisData({ companyName: 'Test Corp' }))
        expect(capturedFilename).toBe('Test_Corp_analysis.csv')
    })

    it('includes company info', () => {
        exportAnalysisDetailCsv(buildAnalysisData())
        expect(capturedContent).toContain('Company,Acme Corp')
        expect(capturedContent).toContain('Industry,SaaS')
        expect(capturedContent).toContain('Overall Risk Score,6.5')
    })

    it('includes risk scores', () => {
        exportAnalysisDetailCsv(buildAnalysisData())
        expect(capturedContent).toContain('Risk Category,Score,Rationale')
        expect(capturedContent).toContain('Competitive Displacement,8,Strong competition')
    })

    it('includes opportunities', () => {
        exportAnalysisDetailCsv(buildAnalysisData())
        expect(capturedContent).toContain('Opportunity,Impact,Timeline')
        expect(capturedContent).toContain('Deploy AI Chatbot,High,Quick Win')
    })

    it('escapes commas in values', () => {
        exportAnalysisDetailCsv(
            buildAnalysisData({
                riskScores: [
                    {
                        category: 'competitive_displacement',
                        score: 8,
                        rationale: 'Strong, aggressive competition',
                    },
                ],
            })
        )
        expect(capturedContent).toContain('"Strong, aggressive competition"')
    })
})

describe('exportAnalysesListCsv', () => {
    it('creates CSV with header and data rows', () => {
        const analyses: AnalysisItem[] = [
            {
                id: 'a-1',
                companyName: 'Acme',
                overallRiskScore: 6.5,
                riskTier: 'high',
                analyzedAt: '2026-03-01',
                scanType: 'portfolio',
            },
        ]
        exportAnalysesListCsv(analyses)
        expect(capturedContent).toContain('Company,Industry,Risk Score,Risk Tier,Source,Analyzed At')
        expect(capturedContent).toContain('Acme,,6.5,high,portfolio,2026-03-01')
    })

    it('uses fixed filename', () => {
        exportAnalysesListCsv([])
        expect(capturedFilename).toBe('analyses_export.csv')
    })

    it('handles multiple rows', () => {
        const analyses: AnalysisItem[] = [
            { id: 'a-1', companyName: 'Alpha', overallRiskScore: 7, riskTier: 'high', analyzedAt: null },
            {
                id: 'a-2',
                companyName: 'Beta',
                overallRiskScore: 3,
                riskTier: 'low',
                analyzedAt: '2026-01-01',
            },
        ]
        exportAnalysesListCsv(analyses)
        const lines = capturedContent.split('\n')
        expect(lines).toHaveLength(3)
    })
})
