/**
 * Minimal AppSync real-time WebSocket client.
 *
 * Implements the AppSync real-time protocol without requiring Amplify or
 * graphql-ws. The protocol is:
 *
 * 1. Connect to wss://{host}/graphql/realtime?header={base64}&payload=e30=
 * 2. Send connection_init → receive connection_ack
 * 3. Send start with subscription query → receive start_ack + data messages
 * 4. Send stop to unsubscribe
 *
 * This is a fire-and-forget enhancement — if it fails, polling takes over.
 */

export interface AppSyncConfig {
    endpoint: string
    apiKey: string
}

export interface AppSyncSubscriptionCallbacks {
    onData: (data: Record<string, unknown>) => void
    onError: () => void
    onClose: () => void
}

const SUBSCRIPTION_ID = '1'

/**
 * Convert the AppSync HTTP endpoint to the realtime WebSocket URL.
 *
 * HTTP:  https://xxx.appsync-api.region.amazonaws.com/graphql
 * WS:   wss://xxx.appsync-realtime-api.region.amazonaws.com/graphql/realtime
 */
function buildRealtimeUrl(config: AppSyncConfig): string {
    const host = new URL(config.endpoint).host
    const authHeader = btoa(
        JSON.stringify({
            host,
            'x-api-key': config.apiKey,
        })
    )

    const wsUrl = config.endpoint
        .replace('https://', 'wss://')
        .replace('appsync-api', 'appsync-realtime-api')
        .replace('/graphql', '/graphql/realtime')

    return `${wsUrl}?header=${encodeURIComponent(authHeader)}&payload=e30=`
}

export function createAppSyncSubscription(
    config: AppSyncConfig,
    query: string,
    variables: Record<string, unknown>,
    callbacks: AppSyncSubscriptionCallbacks
): () => void {
    const url = buildRealtimeUrl(config)
    const host = new URL(config.endpoint).host

    let socket: WebSocket | null = null
    let keepAliveTimer: ReturnType<typeof setTimeout> | null = null
    let disposed = false

    function cleanup(): void {
        disposed = true
        if (keepAliveTimer) {
            clearTimeout(keepAliveTimer)
            keepAliveTimer = null
        }
        if (socket && socket.readyState <= WebSocket.OPEN) {
            try {
                socket.send(JSON.stringify({ type: 'stop', id: SUBSCRIPTION_ID }))
                socket.close()
            } catch {
                // Already closed
            }
        }
        socket = null
    }

    try {
        socket = new WebSocket(url, ['graphql-ws'])
    } catch {
        callbacks.onError()
        return cleanup
    }

    socket.onopen = () => {
        if (disposed) return
        socket?.send(JSON.stringify({ type: 'connection_init' }))
    }

    socket.onmessage = (event: MessageEvent) => {
        if (disposed) return
        const message = JSON.parse(event.data as string) as {
            type: string
            payload?: {
                data?: Record<string, unknown>
                connectionTimeoutMs?: number
            }
        }

        switch (message.type) {
            case 'connection_ack': {
                // Start the subscription after connection is acknowledged
                const subscriptionPayload = {
                    type: 'start',
                    id: SUBSCRIPTION_ID,
                    payload: {
                        data: JSON.stringify({ query, variables }),
                        extensions: {
                            authorization: {
                                host,
                                'x-api-key': config.apiKey,
                            },
                        },
                    },
                }
                socket?.send(JSON.stringify(subscriptionPayload))

                // Set up keep-alive based on server timeout
                const timeoutMs = message.payload?.connectionTimeoutMs ?? 300000
                keepAliveTimer = setTimeout(() => {
                    cleanup()
                    callbacks.onClose()
                }, timeoutMs)
                break
            }
            case 'data': {
                if (message.payload?.data) {
                    callbacks.onData(message.payload.data)
                }
                break
            }
            case 'ka': {
                // Keep-alive — reset timeout
                if (keepAliveTimer) clearTimeout(keepAliveTimer)
                keepAliveTimer = setTimeout(() => {
                    cleanup()
                    callbacks.onClose()
                }, 300000)
                break
            }
            case 'error': {
                callbacks.onError()
                cleanup()
                break
            }
        }
    }

    socket.onerror = () => {
        if (!disposed) callbacks.onError()
        cleanup()
    }

    socket.onclose = () => {
        if (!disposed) callbacks.onClose()
        cleanup()
    }

    return cleanup
}
