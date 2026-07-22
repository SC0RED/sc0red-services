import { describe, it, expect } from 'vitest'

import { isValidMcpUrl } from '@/lib/utils/mcp'

describe('isValidMcpUrl', () => {
    it('accepts an https URL ending in /mcp', () => {
        expect(isValidMcpUrl('https://mcp.prod.services.sc0red.ai/mcp')).toBe(true)
    })

    it('rejects empty / null / undefined', () => {
        expect(isValidMcpUrl('')).toBe(false)
        expect(isValidMcpUrl(null)).toBe(false)
        expect(isValidMcpUrl(undefined)).toBe(false)
    })

    it('rejects non-https and non-/mcp URLs', () => {
        expect(isValidMcpUrl('http://mcp.prod.services.sc0red.ai/mcp')).toBe(false)
        expect(isValidMcpUrl('https://mcp.prod.services.sc0red.ai/')).toBe(false)
        expect(isValidMcpUrl('not a url')).toBe(false)
    })
})
