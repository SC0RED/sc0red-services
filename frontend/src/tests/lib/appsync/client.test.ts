import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import {
    createAppSyncSubscription,
    type AppSyncConfig,
    type AppSyncSubscriptionCallbacks,
} from '@/lib/appsync/client'

const TEST_CONFIG: AppSyncConfig = {
    endpoint: 'https://xxx.appsync-api.us-east-1.amazonaws.com/graphql',
    apiKey: 'da2-fakekey123',
}

const TEST_QUERY = 'subscription OnProgress($scanId: String!) { onScanProgress(scanId: $scanId) { scanId } }'
const TEST_VARIABLES = { scanId: 'scan-1' }

class MockWebSocket {
    static instances: MockWebSocket[] = []
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3

    url: string
    protocols: string | string[]
    readyState: number = 0 // CONNECTING
    onopen: ((event: Event) => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null
    onerror: ((event: Event) => void) | null = null
    onclose: ((event: CloseEvent) => void) | null = null

    sent: string[] = []
    closed = false

    constructor(url: string, protocols?: string | string[]) {
        this.url = url
        this.protocols = protocols ?? ''
        MockWebSocket.instances.push(this)
    }

    send(data: string): void {
        this.sent.push(data)
    }

    close(): void {
        this.closed = true
        this.readyState = 3 // CLOSED
    }

    simulateOpen(): void {
        this.readyState = 1 // OPEN
        if (this.onopen) this.onopen(new Event('open'))
    }

    simulateMessage(data: Record<string, unknown>): void {
        if (this.onmessage) {
            this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
        }
    }

    simulateError(): void {
        if (this.onerror) this.onerror(new Event('error'))
    }

    simulateClose(): void {
        if (this.onclose) this.onclose({ code: 1000, reason: '', wasClean: true } as CloseEvent)
    }
}

describe('createAppSyncSubscription', () => {
    let originalWebSocket: typeof globalThis.WebSocket

    beforeEach(() => {
        MockWebSocket.instances = []
        originalWebSocket = globalThis.WebSocket
        globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket
    })

    afterEach(() => {
        globalThis.WebSocket = originalWebSocket
        vi.restoreAllMocks()
    })

    function makeCallbacks(): AppSyncSubscriptionCallbacks {
        return {
            onData: vi.fn(),
            onError: vi.fn(),
            onClose: vi.fn(),
        }
    }

    it('creates a WebSocket with correct realtime URL', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        expect(MockWebSocket.instances).toHaveLength(1)
        const socket = MockWebSocket.instances[0]
        expect(socket.url).toContain('wss://')
        expect(socket.url).toContain('appsync-realtime-api')
        expect(socket.url).toContain('/graphql/realtime')
        expect(socket.protocols).toEqual(['graphql-ws'])
    })

    it('sends connection_init on open', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateOpen()

        expect(socket.sent).toHaveLength(1)
        expect(JSON.parse(socket.sent[0])).toEqual({ type: 'connection_init' })
    })

    it('sends start subscription after connection_ack', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateOpen()
        socket.simulateMessage({ type: 'connection_ack', payload: { connectionTimeoutMs: 300000 } })

        expect(socket.sent).toHaveLength(2)
        const startMessage = JSON.parse(socket.sent[1])
        expect(startMessage.type).toBe('start')
        expect(startMessage.id).toBe('1')
        const payloadData = JSON.parse(startMessage.payload.data)
        expect(payloadData.query).toBe(TEST_QUERY)
        expect(payloadData.variables).toEqual(TEST_VARIABLES)
    })

    it('calls onData when data message is received', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateOpen()
        socket.simulateMessage({ type: 'connection_ack' })

        const testData = { onScanProgress: { scanId: 'scan-1', progress: 50 } }
        socket.simulateMessage({ type: 'data', payload: { data: testData } })

        expect(callbacks.onData).toHaveBeenCalledWith(testData)
    })

    it('calls onError on WebSocket error', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateError()

        expect(callbacks.onError).toHaveBeenCalled()
    })

    it('calls onClose on WebSocket close', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateClose()

        expect(callbacks.onClose).toHaveBeenCalled()
    })

    it('calls onError on protocol error message', () => {
        const callbacks = makeCallbacks()
        createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.simulateOpen()
        socket.simulateMessage({ type: 'error' })

        expect(callbacks.onError).toHaveBeenCalled()
    })

    it('returns a cleanup function that sends stop and closes', () => {
        const callbacks = makeCallbacks()
        const cleanup = createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        // Simulate open so the socket is in OPEN state (readyState = 1)
        socket.simulateOpen()
        socket.readyState = 1 // WebSocket.OPEN

        cleanup()

        expect(socket.sent.some((message) => JSON.parse(message).type === 'stop')).toBe(true)
        expect(socket.closed).toBe(true)
    })

    it('does not call callbacks after cleanup (disposed)', () => {
        const callbacks = makeCallbacks()
        const cleanup = createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        const socket = MockWebSocket.instances[0]
        socket.readyState = WebSocket.OPEN
        cleanup()

        // These should be no-ops after disposal
        socket.simulateClose()
        socket.simulateError()

        expect(callbacks.onClose).not.toHaveBeenCalled()
        expect(callbacks.onError).not.toHaveBeenCalled()
    })

    it('calls onError when WebSocket constructor throws', () => {
        globalThis.WebSocket = class {
            constructor() {
                throw new Error('WebSocket not supported')
            }
        } as unknown as typeof WebSocket

        const callbacks = makeCallbacks()
        const cleanup = createAppSyncSubscription(TEST_CONFIG, TEST_QUERY, TEST_VARIABLES, callbacks)

        expect(callbacks.onError).toHaveBeenCalled()
        expect(typeof cleanup).toBe('function')
    })
})
