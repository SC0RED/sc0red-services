import { describe, it, expect } from 'vitest'

import { BackendError } from '@/lib/api/errors'

describe('BackendError', () => {
    it('extends the built-in Error class', () => {
        const error = new BackendError('Not found', 404)
        expect(error).toBeInstanceOf(Error)
    })

    it('is also an instance of BackendError', () => {
        const error = new BackendError('Not found', 404)
        expect(error).toBeInstanceOf(BackendError)
    })

    it('has name set to "BackendError"', () => {
        const error = new BackendError('Not found', 404)
        expect(error.name).toBe('BackendError')
    })

    it('stores the error message', () => {
        const error = new BackendError('Unauthorized', 401)
        expect(error.message).toBe('Unauthorized')
    })

    it('stores the HTTP status code', () => {
        const error = new BackendError('Not found', 404)
        expect(error.status).toBe(404)
    })

    it('status is readonly (not accidentally mutated)', () => {
        const error = new BackendError('Server error', 500)
        expect(error.status).toBe(500)
    })

    it('works correctly with different status codes', () => {
        expect(new BackendError('Bad Request', 400).status).toBe(400)
        expect(new BackendError('Unauthorized', 401).status).toBe(401)
        expect(new BackendError('Forbidden', 403).status).toBe(403)
        expect(new BackendError('Not Found', 404).status).toBe(404)
        expect(new BackendError('Internal Server Error', 500).status).toBe(500)
    })
})
