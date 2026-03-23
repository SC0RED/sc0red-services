import { describe, it, expect } from 'vitest'

import { BackendError } from '@/lib/api/errors'
import { handleRouteError } from '@/lib/api/routeError'

describe('handleRouteError', () => {
    it('returns 500 for generic Error', async () => {
        const response = handleRouteError(new Error('Something went wrong'))

        expect(response.status).toBe(500)
        const body = await response.json()
        expect(body.error).toBe('Something went wrong')
    })

    it('returns specific status for BackendError', async () => {
        const response = handleRouteError(new BackendError('Not found', 404))

        expect(response.status).toBe(404)
        const body = await response.json()
        expect(body.error).toBe('Not found')
    })

    it('returns 500 for non-Error unknown', async () => {
        const response = handleRouteError('string error')

        expect(response.status).toBe(500)
        const body = await response.json()
        expect(body.error).toBe('Internal Server Error')
    })

    it('returns 500 for null', async () => {
        const response = handleRouteError(null)

        expect(response.status).toBe(500)
        const body = await response.json()
        expect(body.error).toBe('Internal Server Error')
    })

    it('response body has error field with message', async () => {
        const response = handleRouteError(new BackendError('Unauthorized', 401))

        const body = await response.json()
        expect(body).toHaveProperty('error')
        expect(body.error).toBe('Unauthorized')
    })
})
