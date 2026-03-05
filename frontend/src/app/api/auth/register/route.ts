import { NextRequest, NextResponse } from 'next/server'
import bcrypt from 'bcryptjs'
import { getDb, generateId, initializeDb } from '@/lib/db/client'

export async function POST(req: NextRequest) {
    const { name, email, password, orgName, orgType } = await req.json()
    if (!name || !email || !password || !orgName) {
        return NextResponse.json({ error: 'All fields required' }, { status: 400 })
    }

    try {
        await initializeDb()
        const db = getDb()

        // Check if email exists
        const existing = await db.execute({ sql: 'SELECT id FROM users WHERE email = ?', args: [email] })
        if (existing.rows.length > 0) {
            return NextResponse.json({ error: 'Email already registered' }, { status: 400 })
        }

        const orgId = generateId()
        const userId = generateId()
        const hash = await bcrypt.hash(password, 10)

        await db.execute({
            sql: `INSERT INTO organizations (id, name, type) VALUES (?, ?, ?)`,
            args: [orgId, orgName, orgType || 'company'],
        })

        await db.execute({
            sql: `INSERT INTO users (id, org_id, email, password_hash, name, role) VALUES (?, ?, ?, ?, ?, 'admin')`,
            args: [userId, orgId, email, hash, name],
        })

        return NextResponse.json({ success: true })
    } catch (err: any) {
        console.error('Register error details:', err?.message, err?.stack, err)
        return NextResponse.json({ error: err.message || 'Registration failed' }, { status: 500 })
    }
}
