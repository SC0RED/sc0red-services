import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

vi.mock('@/lib/appsync/client', () => ({
    createAppSyncSubscription: vi.fn(),
}))

import { createAppSyncSubscription } from '@/lib/appsync/client'
import { useScanRealtime } from '@/lib/hooks/useScanRealtime'

const mockCreateSubscription = vi.mocked(createAppSyncSubscription)

describe('useScanRealtime', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    function makeOptions() {
        return {
            onProgress: vi.fn(),
            onComplete: vi.fn(),
            onFailed: vi.fn(),
        }
    }

    it('fetches /api/config when start is called', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ appsyncEndpoint: '', appsyncApiKey: '' }),
        })
        global.fetch = fetchMock

        const options = makeOptions()
        const { result } = renderHook(() => useScanRealtime(options))

        await act(async () => {
            result.current.start('scan-1')
        })

        expect(fetchMock).toHaveBeenCalledWith('/api/config')
    })

    it('does not subscribe when AppSync is not configured (empty endpoint)', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () => Promise.resolve({ appsyncEndpoint: '', appsyncApiKey: '' }),
        })
        global.fetch = fetchMock

        const options = makeOptions()
        const { result } = renderHook(() => useScanRealtime(options))

        await act(async () => {
            result.current.start('scan-1')
        })

        expect(mockCreateSubscription).not.toHaveBeenCalled()
    })

    it('creates subscription when AppSync is configured', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () =>
                Promise.resolve({
                    appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
                    appsyncApiKey: 'da2-fakekey',
                }),
        })
        global.fetch = fetchMock

        const mockUnsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(mockUnsubscribe)

        const options = makeOptions()
        const { result } = renderHook(() => useScanRealtime(options))

        await act(async () => {
            result.current.start('scan-1')
        })

        expect(mockCreateSubscription).toHaveBeenCalledTimes(1)
        const callArgs = mockCreateSubscription.mock.calls[0]
        expect(callArgs[0]).toEqual({
            endpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
            apiKey: 'da2-fakekey',
        })
        expect(callArgs[2]).toEqual({ scanId: 'scan-1' })
    })

    it('calls cleanup on stop', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () =>
                Promise.resolve({
                    appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
                    appsyncApiKey: 'da2-fakekey',
                }),
        })
        global.fetch = fetchMock

        const mockUnsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(mockUnsubscribe)

        const options = makeOptions()
        const { result } = renderHook(() => useScanRealtime(options))

        await act(async () => {
            result.current.start('scan-1')
        })

        act(() => {
            result.current.stop()
        })

        expect(mockUnsubscribe).toHaveBeenCalled()
    })

    it('cleans up on unmount', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            json: () =>
                Promise.resolve({
                    appsyncEndpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
                    appsyncApiKey: 'da2-fakekey',
                }),
        })
        global.fetch = fetchMock

        const mockUnsubscribe = vi.fn()
        mockCreateSubscription.mockReturnValue(mockUnsubscribe)

        const options = makeOptions()
        const { result, unmount } = renderHook(() => useScanRealtime(options))

        await act(async () => {
            result.current.start('scan-1')
        })

        unmount()

        expect(mockUnsubscribe).toHaveBeenCalled()
    })

    it('silently handles config fetch failure', async () => {
        const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'))
        global.fetch = fetchMock

        const options = makeOptions()
        const { result } = renderHook(() => useScanRealtime(options))

        // Should not throw
        await act(async () => {
            result.current.start('scan-1')
        })

        expect(mockCreateSubscription).not.toHaveBeenCalled()
    })
})
