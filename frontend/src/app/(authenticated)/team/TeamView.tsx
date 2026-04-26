'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'

import { useToast } from '@/components/ui'

interface Member {
    id: string
    email: string
    name: string
    role: string
}

interface PendingInvitation {
    id: string
    email: string
    role: string
    status: string
    invitedAt: string
}

interface TeamViewProps {
    initialMembers: Member[]
    initialInvitations: PendingInvitation[]
}

export default function TeamView({ initialMembers, initialInvitations }: TeamViewProps) {
    const { data: session } = useSession()
    const toast = useToast()
    const [members, setMembers] = useState(initialMembers)
    const [invitations, setInvitations] = useState(initialInvitations)
    const [inviteEmail, setInviteEmail] = useState('')
    const [inviteRole, setInviteRole] = useState<'analyst' | 'viewer'>('analyst')
    const [inviting, setInviting] = useState(false)

    async function handleInvite(e: React.FormEvent) {
        e.preventDefault()
        setInviting(true)

        try {
            const res = await fetch('/api/org/invite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
            })
            const data = await res.json()

            if (!res.ok) {
                toast.error(data.error || 'Failed to send invitation')
                return
            }

            toast.success(`Invitation sent to ${inviteEmail}`)
            const sentTo = inviteEmail
            setInviteEmail('')
            setInvitations((prev) => [
                ...prev,
                {
                    id: data.invitationId,
                    email: sentTo,
                    role: inviteRole,
                    status: 'pending',
                    invitedAt: new Date().toISOString(),
                },
            ])
        } catch {
            toast.error('Failed to send invitation')
        } finally {
            setInviting(false)
        }
    }

    async function handleResendInvite(email: string) {
        try {
            const res = await fetch('/api/org/invite/resend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            })
            if (res.ok) {
                toast.success(`Invitation resent to ${email}`)
            } else {
                const data = await res.json()
                toast.error(data.error || 'Failed to resend invitation')
            }
        } catch {
            toast.error('Failed to resend invitation')
        }
    }

    async function handleRevokeInvite(inviteId: string, email: string) {
        // TODO: convert to toast.undo pattern in a follow-up; needs a small
        // refactor to reconcile the optimistic list update with deferred-commit
        // semantics. Keeping the confirm() dialog for now to keep this PR tight.
        if (!confirm(`Revoke invitation for ${email}?`)) return

        try {
            const res = await fetch(`/api/org/invite/${inviteId}`, { method: 'DELETE' })
            if (res.ok) {
                setInvitations((prev) => prev.filter((inv) => inv.id !== inviteId))
                toast.success(`Revoked invitation for ${email}`)
            } else {
                toast.error('Failed to revoke invitation')
            }
        } catch {
            toast.error('Failed to revoke invitation')
        }
    }

    async function handleRemove(userId: string, email: string) {
        // Same TODO as handleRevokeInvite — toast.undo follow-up.
        if (!confirm(`Remove ${email} from the team?`)) return

        try {
            const res = await fetch(`/api/org/members/${userId}`, { method: 'DELETE' })
            if (res.ok) {
                setMembers((prev) => prev.filter((m) => m.id !== userId))
                toast.success(`Removed ${email} from the team`)
            } else {
                toast.error('Failed to remove member')
            }
        } catch {
            toast.error('Failed to remove member')
        }
    }

    return (
        <div style={{ maxWidth: '720px' }}>
            <div style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                    Team Management
                </h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Invite members to your organisation and manage access.
                </p>
            </div>

            {/* Invite form */}
            <div className="card" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Invite Member</h2>
                <form
                    onSubmit={handleInvite}
                    style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}
                >
                    <div className="input-group" style={{ flex: 1, minWidth: '200px' }}>
                        <label className="label" htmlFor="invite-email">
                            Email
                        </label>
                        <input
                            id="invite-email"
                            type="email"
                            className="input"
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                            placeholder="colleague@company.com"
                            required
                        />
                    </div>
                    <div className="input-group" style={{ width: '140px' }}>
                        <label className="label" htmlFor="invite-role">
                            Role
                        </label>
                        <select
                            id="invite-role"
                            className="input"
                            value={inviteRole}
                            onChange={(e) => setInviteRole(e.target.value as 'analyst' | 'viewer')}
                        >
                            <option value="analyst">Analyst</option>
                            <option value="viewer">Viewer</option>
                        </select>
                    </div>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={inviting}
                        style={{ height: '40px' }}
                    >
                        {inviting ? 'Sending...' : 'Send Invite'}
                    </button>
                </form>
            </div>

            {/* Members list */}
            <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
                <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
                    Members ({members.length})
                </h2>
                {members.length === 0 ? (
                    <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>No members yet.</p>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {members.map((member) => (
                            <div
                                key={member.id}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.75rem',
                                    padding: '0.75rem',
                                    borderRadius: 'var(--radius-md)',
                                    background: 'var(--bg-surface-2)',
                                }}
                            >
                                <div
                                    style={{
                                        width: '32px',
                                        height: '32px',
                                        borderRadius: '50%',
                                        background:
                                            'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '0.75rem',
                                        fontWeight: 700,
                                        color: '#fff',
                                        flexShrink: 0,
                                    }}
                                >
                                    {member.name?.[0]?.toUpperCase() || member.email[0].toUpperCase()}
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>
                                        {member.name || member.email}
                                    </div>
                                    <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                                        {member.email}
                                    </div>
                                </div>
                                <span
                                    style={{
                                        fontSize: '0.6875rem',
                                        fontWeight: 600,
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        padding: '0.25rem 0.5rem',
                                        borderRadius: 'var(--radius-sm)',
                                        background:
                                            member.role === 'admin'
                                                ? 'rgba(59,123,246,0.1)'
                                                : 'var(--bg-surface-3)',
                                        color:
                                            member.role === 'admin'
                                                ? 'var(--accent-blue)'
                                                : 'var(--text-secondary)',
                                    }}
                                >
                                    {member.role}
                                </span>
                                {member.id !== session?.user?.id && (
                                    <button
                                        onClick={() => handleRemove(member.id, member.email)}
                                        style={{
                                            background: 'none',
                                            border: 'none',
                                            color: 'var(--text-tertiary)',
                                            cursor: 'pointer',
                                            padding: '4px',
                                        }}
                                        title={`Remove ${member.email}`}
                                        aria-label={`Remove ${member.email}`}
                                    >
                                        <svg
                                            width="14"
                                            height="14"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                        >
                                            <line x1="18" y1="6" x2="6" y2="18" />
                                            <line x1="6" y1="6" x2="18" y2="18" />
                                        </svg>
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Pending invitations */}
            {invitations.length > 0 && (
                <div className="card" style={{ padding: '1.5rem' }}>
                    <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
                        Pending Invitations ({invitations.length})
                    </h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {invitations.map((invitation) => (
                            <div
                                key={invitation.id}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.75rem',
                                    padding: '0.75rem',
                                    borderRadius: 'var(--radius-md)',
                                    background: 'var(--bg-surface-2)',
                                    opacity: 0.7,
                                }}
                            >
                                <div
                                    style={{
                                        width: '32px',
                                        height: '32px',
                                        borderRadius: '50%',
                                        background: 'var(--bg-surface-3)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '0.75rem',
                                        color: 'var(--text-tertiary)',
                                        flexShrink: 0,
                                    }}
                                >
                                    ?
                                </div>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>
                                        {invitation.email}
                                    </div>
                                    <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                                        Invited as {invitation.role}
                                    </div>
                                </div>
                                <span
                                    style={{
                                        fontSize: '0.6875rem',
                                        fontWeight: 600,
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        padding: '0.25rem 0.5rem',
                                        borderRadius: 'var(--radius-sm)',
                                        background: 'rgba(245,158,11,0.1)',
                                        color: 'var(--risk-moderate)',
                                    }}
                                >
                                    Pending
                                </span>
                                <button
                                    onClick={() => handleResendInvite(invitation.email)}
                                    className="btn btn-ghost"
                                    style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                                    title="Resend invitation email"
                                >
                                    Resend
                                </button>
                                <button
                                    onClick={() => handleRevokeInvite(invitation.id, invitation.email)}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: 'var(--text-tertiary)',
                                        cursor: 'pointer',
                                        padding: '4px',
                                    }}
                                    title={`Revoke invitation for ${invitation.email}`}
                                    aria-label={`Revoke invitation for ${invitation.email}`}
                                >
                                    <svg
                                        width="14"
                                        height="14"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    >
                                        <line x1="18" y1="6" x2="6" y2="18" />
                                        <line x1="6" y1="6" x2="18" y2="18" />
                                    </svg>
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
