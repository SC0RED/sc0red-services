import { NextRequest, NextResponse } from 'next/server'

import { backendFetch } from '@/lib/api/serverToken'

/**
 * POST /api/oauth/approve — User approves OAuth consent.
 *
 * Called by the consent UI after user clicks "Allow Access".
 * Forwards to the backend which generates an authorization code
 * and returns the redirect URL with the code.
 */
export async function POST(request: NextRequest) {
    try {
        const body = await request.json()

        // Pass the parsed object — `backendFetch` JSON-stringifies the body
        // itself. Passing `JSON.stringify(body)` here double-encodes it, so the
        // backend's `json.loads(event["body"])` yields a string (not a dict) and
        // `handle_oauth_approve` throws `AttributeError: 'str' object has no
        // attribute 'get'` → 502. Match the convention used by every other
        // backendFetch POST caller (e.g. /api/org/invite).
        const data = await backendFetch<{ redirect_url: string }>('/api/oauth/approve', {
            method: 'POST',
            body,
        })

        return NextResponse.json(data)
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Authorization failed'
        return NextResponse.json({ error: message }, { status: 500 })
    }
}
