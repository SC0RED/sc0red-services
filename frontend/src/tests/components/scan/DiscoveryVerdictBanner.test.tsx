import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import DiscoveryVerdictBanner from '@/components/scan/DiscoveryVerdictBanner'
import type { DiscoveryVerdict } from '@/lib/types/scan'

function makeVerdict(overrides: Partial<DiscoveryVerdict> = {}): DiscoveryVerdict {
    return {
        method: 'none',
        count: 0,
        completeness: 'genuinely_empty',
        availableActions: ['upload_list', 'search_deeper'],
        ...overrides,
    }
}

function renderBanner(verdict: DiscoveryVerdict, currentCount = verdict.count) {
    return render(
        <DiscoveryVerdictBanner
            verdict={verdict}
            currentCount={currentCount}
            onUploadList={vi.fn()}
            onSearchDeeper={vi.fn()}
            uploadOpen={false}
        />
    )
}

describe('DiscoveryVerdictBanner — delivery mechanism hint', () => {
    it('explains an opaque (client-side-rendered) shell so the empty result is not mistaken for "no portfolio"', () => {
        renderBanner(makeVerdict({ deliveryMechanism: 'opaque_shell' }))
        expect(screen.getByText(/render its portfolio in the browser/i)).toBeInTheDocument()
    })

    it('explains an unreachable site', () => {
        renderBanner(makeVerdict({ completeness: 'site_blocked', deliveryMechanism: 'unreachable' }))
        expect(screen.getByText(/blocked our request this run/i)).toBeInTheDocument()
    })

    it('explains a page with no portfolio section', () => {
        renderBanner(makeVerdict({ deliveryMechanism: 'no_portfolio_found' }))
        expect(screen.getByText(/found no portfolio section/i)).toBeInTheDocument()
    })

    it('shows no mechanism hint for a self-evident static listing', () => {
        renderBanner(
            makeVerdict({
                completeness: 'full_site_list',
                count: 12,
                deliveryMechanism: 'static_listing',
            })
        )
        expect(screen.queryByText(/render its portfolio in the browser/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/found no portfolio section/i)).not.toBeInTheDocument()
    })

    it('shows no mechanism hint when deliveryMechanism is absent (older verdicts)', () => {
        renderBanner(makeVerdict())
        // Falls back to the completeness message only, no extra "why" line.
        expect(screen.queryByText(/render its portfolio in the browser/i)).not.toBeInTheDocument()
        expect(
            screen.getByText(/couldn’t find this firm’s portfolio companies automatically/i)
        ).toBeInTheDocument()
    })
})
