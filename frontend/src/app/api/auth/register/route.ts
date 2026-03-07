import { NextRequest, NextResponse } from 'next/server'
import { BACKEND_URL } from '@/lib/config'

export async function POST(req: NextRequest) {
    try {
        const body = await req.json()
        const response = await fetch(`${BACKEND_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
        const data = await response.json()
        return NextResponse.json(data, { status: response.status })
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Registration failed'
        return NextResponse.json({ error: message }, { status: 500 })
    }
}
