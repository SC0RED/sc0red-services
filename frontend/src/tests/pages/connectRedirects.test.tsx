import { vi, describe, it, expect, beforeEach } from 'vitest'

const mockRedirect = vi.fn()
vi.mock('next/navigation', () => ({
    redirect: (path: string) => mockRedirect(path),
}))

import SettingsConnectRedirect from '@/app/(authenticated)/settings/connect/page'
import ConnectedAppsRedirect from '@/app/(authenticated)/settings/connected-apps/page'

describe('legacy Connect route redirects', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('/settings/connect redirects to /connect', () => {
        SettingsConnectRedirect()
        expect(mockRedirect).toHaveBeenCalledWith('/connect')
    })

    it('/settings/connected-apps redirects to /connect', () => {
        ConnectedAppsRedirect()
        expect(mockRedirect).toHaveBeenCalledWith('/connect')
    })
})
