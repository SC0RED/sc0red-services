import 'next-auth'
import 'next-auth/jwt'

declare module 'next-auth' {
    interface User {
        id: string
        orgId: string
        role: string
        idToken?: string
    }
    interface Session {
        user: User & { email: string; name?: string | null; idToken?: string }
    }
}

declare module 'next-auth/jwt' {
    interface JWT {
        id?: string
        orgId?: string
        role?: string
        idToken?: string
    }
}
