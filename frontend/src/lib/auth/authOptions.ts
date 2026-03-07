import { NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'

import { BACKEND_URL } from '@/lib/config'

export const authOptions: NextAuthOptions = {
    providers: [
        CredentialsProvider({
            name: 'credentials',
            credentials: {
                email: { label: 'Email', type: 'email' },
                password: { label: 'Password', type: 'password' },
            },
            async authorize(credentials) {
                if (!credentials?.email || !credentials?.password) return null
                try {
                    const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            email: credentials.email,
                            password: credentials.password,
                        }),
                    })

                    if (!response.ok) return null

                    const data = (await response.json()) as {
                        success: boolean
                        user: { id: string; email: string; name: string; orgId: string; role: string }
                    }
                    if (!data.success || !data.user) return null

                    return {
                        id: data.user.id,
                        email: data.user.email,
                        name: data.user.name,
                        orgId: data.user.orgId,
                        role: data.user.role,
                    }
                } catch {
                    return null
                }
            },
        }),
    ],
    session: { strategy: 'jwt' },
    callbacks: {
        async jwt({ token, user }) {
            if (user) {
                token.orgId = user.orgId
                token.role = user.role
                token.id = user.id
            }
            return token
        },
        async session({ session, token }) {
            if (session.user) {
                session.user.orgId = token.orgId ?? ''
                session.user.role = token.role ?? ''
                session.user.id = token.id ?? ''
            }
            return session
        },
    },
    pages: { signIn: '/login' },
    secret: process.env.NEXTAUTH_SECRET,
    jwt: {
        maxAge: 30 * 24 * 60 * 60, // 30 days
    },
}
