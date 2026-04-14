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

        const data = await backendFetch<{ redirect_url: string }>('/api/oauth/approve', {
            method: 'POST',
            body: JSON.stringify(body),
        })

        return NextResponse.json(data)
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Authorization failed'
        return NextResponse.json({ error: message }, { status: 500 })
    }
}
