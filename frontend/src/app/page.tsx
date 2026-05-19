import { redirect } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { getServerSession } from 'next-auth'

import { authOptions } from '@/lib/auth/authOptions'
import { TIER_COLORS } from '@/lib/utils/riskUtils'

export default async function LandingPage() {
    const session = await getServerSession(authOptions)
    if (session) {
        redirect('/dashboard')
    }

    const features = [
        {
            icon: (
                <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
            ),
            title: 'Portfolio Intelligence',
            desc: 'Enter any PE firm URL and auto-discover all portfolio companies. Get a risk assessment for every company in minutes.',
            color: 'var(--accent-blue)',
        },
        {
            icon: (
                <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <polygon points="12 2 2 7 12 12 22 7 12 2" />
                    <polyline points="2 17 12 22 22 17" />
                    <polyline points="2 12 12 17 22 12" />
                </svg>
            ),
            title: '8-Dimension Risk Framework',
            desc: 'Score across Competitive Displacement, Technology Obsolescence, Workforce Disruption, Margin Compression, and 4 more AI risk vectors.',
            color: 'var(--accent-cyan)',
        },
        {
            icon: (
                <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
            ),
            title: 'Tactical Action Plans',
            desc: 'Go beyond diagnosis. Get specific implementation steps, ROI estimates, investment ranges, and vetted implementation partners for every opportunity.',
            color: 'var(--risk-moderate)',
        },
    ]

    const risks = [
        { name: 'Competitive Displacement', score: 8.2, tier: 'critical' },
        { name: 'Tech Obsolescence', score: 6.8, tier: 'high' },
        { name: 'Margin Compression', score: 5.9, tier: 'moderate' },
        { name: 'Workforce Disruption', score: 4.2, tier: 'moderate' },
        { name: 'Customer Behavior', score: 7.1, tier: 'high' },
        { name: 'Regulatory Risk', score: 3.1, tier: 'low' },
    ]

    return (
        <div style={{ minHeight: '100vh' }}>
            {/* Nav */}
            <nav
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    zIndex: 100,
                    background: 'rgba(6,10,18,0.8)',
                    backdropFilter: 'blur(16px)',
                    borderBottom: '1px solid var(--border-subtle)',
                    padding: '0 2rem',
                    height: '64px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                    <div
                        style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '7px',
                            overflow: 'hidden',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}
                    >
                        <Image
                            src="/sc0red-advisory-logo.svg"
                            alt="sc0red Advisory"
                            width={40}
                            height={40}
                            style={{ objectFit: 'contain' }}
                        />
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1rem' }}>sc0red Advisory</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <Link href="/login" className="btn btn-ghost btn-sm">
                        Sign In
                    </Link>
                    <Link href="/signup" className="btn btn-primary btn-sm">
                        Get Started
                    </Link>
                </div>
            </nav>

            {/* Hero */}
            <section
                style={{
                    textAlign: 'center',
                    padding: '140px 2rem 100px',
                    position: 'relative',
                    overflow: 'hidden',
                }}
                className="grid-bg"
            >
                <div
                    style={{
                        position: 'absolute',
                        inset: 0,
                        zIndex: 0,
                        background:
                            'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(59,123,246,0.12) 0%, transparent 70%)',
                    }}
                />
                <div style={{ position: 'relative', zIndex: 1, maxWidth: '860px', margin: '0 auto' }}>
                    <div
                        className="badge badge-blue"
                        style={{ marginBottom: '1.5rem', fontSize: '0.8125rem' }}
                    >
                        <span
                            style={{
                                width: '6px',
                                height: '6px',
                                borderRadius: '50%',
                                background: 'var(--accent-blue)',
                                display: 'inline-block',
                                animation: 'pulse 2s infinite',
                            }}
                        />
                        AI-Powered Risk Intelligence for Private Equity
                    </div>
                    <h1
                        style={{
                            fontSize: 'clamp(2.5rem, 6vw, 4rem)',
                            fontWeight: 800,
                            lineHeight: 1.1,
                            letterSpacing: '-0.03em',
                            marginBottom: '1.5rem',
                        }}
                    >
                        Know Your AI Risk.
                        <br />
                        <span
                            style={{
                                background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                            }}
                        >
                            Capture the Opportunity.
                        </span>
                    </h1>
                    <p
                        style={{
                            fontSize: '1.25rem',
                            color: 'var(--text-secondary)',
                            maxWidth: '600px',
                            margin: '0 auto 2.5rem',
                            lineHeight: 1.7,
                        }}
                    >
                        sc0red Advisory analyzes your portfolio companies for AI-driven disruption risks and
                        generates specific, tactical roadmaps to defend and grow.
                    </p>
                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                        <Link href="/signup" className="btn btn-primary btn-lg">
                            <svg
                                width="17"
                                height="17"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <circle cx="11" cy="11" r="8" />
                                <path d="m21 21-4.35-4.35" />
                            </svg>
                            Analyze Your Portfolio Free
                        </Link>
                        <Link href="/login" className="btn btn-ghost btn-lg">
                            Sign In
                        </Link>
                    </div>
                    <p style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                        No credit card required · Analysis in minutes · Powered by AI
                    </p>
                </div>
            </section>

            {/* Demo Preview */}
            <section style={{ padding: '0 2rem 6rem', maxWidth: '1100px', margin: '0 auto' }}>
                <div className="card" style={{ overflow: 'hidden' }}>
                    {/* Mock analysis preview */}
                    <div
                        style={{
                            padding: '1.25rem 1.5rem',
                            borderBottom: '1px solid var(--border-subtle)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '1rem',
                        }}
                    >
                        <div style={{ display: 'flex', gap: '6px' }}>
                            {['var(--risk-critical)', 'var(--risk-moderate)', 'var(--risk-low)'].map(
                                (c, i) => (
                                    <div
                                        key={i}
                                        style={{
                                            width: '12px',
                                            height: '12px',
                                            borderRadius: '50%',
                                            background: c,
                                            opacity: 0.7,
                                        }}
                                    />
                                )
                            )}
                        </div>
                        <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                            sc0red Advisory Analysis — Acme Financial Services
                        </span>
                    </div>
                    <div
                        style={{
                            padding: '1.5rem',
                            display: 'grid',
                            gridTemplateColumns: '200px 1fr',
                            gap: '1.5rem',
                        }}
                    >
                        <div
                            style={{
                                textAlign: 'center',
                                padding: '1.5rem',
                                background: 'var(--bg-surface-2)',
                                borderRadius: 'var(--radius-md)',
                            }}
                        >
                            <div
                                style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--text-tertiary)',
                                    marginBottom: '0.75rem',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.08em',
                                }}
                            >
                                Risk Score
                            </div>
                            <div
                                style={{
                                    fontSize: '3.5rem',
                                    fontWeight: 800,
                                    color: 'var(--risk-high)',
                                    lineHeight: 1,
                                }}
                            >
                                7.4
                            </div>
                            <div className="badge badge-high" style={{ marginTop: '0.75rem' }}>
                                High Risk
                            </div>
                        </div>
                        <div>
                            <div
                                style={{
                                    marginBottom: '0.75rem',
                                    fontWeight: 600,
                                    fontSize: '0.875rem',
                                    color: 'var(--text-secondary)',
                                }}
                            >
                                Risk Assessment
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                {risks.map((r) => (
                                    <div
                                        key={r.name}
                                        style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}
                                    >
                                        <div
                                            style={{
                                                width: '140px',
                                                fontSize: '0.8rem',
                                                color: 'var(--text-secondary)',
                                                flexShrink: 0,
                                            }}
                                        >
                                            {r.name}
                                        </div>
                                        <div
                                            style={{
                                                flex: 1,
                                                height: '6px',
                                                background: 'var(--bg-surface-3)',
                                                borderRadius: '3px',
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    height: '100%',
                                                    width: `${(r.score / 10) * 100}%`,
                                                    background: TIER_COLORS[r.tier],
                                                    borderRadius: '3px',
                                                }}
                                            />
                                        </div>
                                        <div
                                            style={{
                                                width: '32px',
                                                fontSize: '0.8rem',
                                                fontWeight: 700,
                                                color: TIER_COLORS[r.tier],
                                                textAlign: 'right',
                                            }}
                                        >
                                            {r.score}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features */}
            <section style={{ padding: '2rem 2rem 6rem', maxWidth: '1100px', margin: '0 auto' }}>
                <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
                    <h2
                        style={{
                            fontSize: '2rem',
                            fontWeight: 700,
                            marginBottom: '0.75rem',
                            letterSpacing: '-0.02em',
                        }}
                    >
                        From risk to roadmap in minutes
                    </h2>
                    <p
                        style={{
                            color: 'var(--text-secondary)',
                            fontSize: '1.0625rem',
                            maxWidth: '500px',
                            margin: '0 auto',
                        }}
                    >
                        Three core capabilities that turn AI disruption into competitive advantage
                    </p>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.25rem' }}>
                    {features.map((f) => (
                        <div key={f.title} className="card" style={{ padding: '1.75rem' }}>
                            <div
                                style={{
                                    width: '48px',
                                    height: '48px',
                                    borderRadius: 'var(--radius-md)',
                                    background: `${f.color}18`,
                                    border: `1px solid ${f.color}30`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: f.color,
                                    marginBottom: '1.25rem',
                                }}
                            >
                                {f.icon}
                            </div>
                            <h3 style={{ fontWeight: 700, marginBottom: '0.625rem', fontSize: '1.0625rem' }}>
                                {f.title}
                            </h3>
                            <p
                                style={{
                                    color: 'var(--text-secondary)',
                                    fontSize: '0.9rem',
                                    lineHeight: 1.7,
                                }}
                            >
                                {f.desc}
                            </p>
                        </div>
                    ))}
                </div>
            </section>

            {/* CTA */}
            <section style={{ padding: '4rem 2rem 6rem', textAlign: 'center' }}>
                <div
                    className="card"
                    style={{
                        maxWidth: '600px',
                        margin: '0 auto',
                        padding: '3rem',
                        borderColor: 'rgba(59,123,246,0.2)',
                    }}
                >
                    <h2
                        style={{
                            fontSize: '1.75rem',
                            fontWeight: 700,
                            marginBottom: '1rem',
                            letterSpacing: '-0.02em',
                        }}
                    >
                        Understand your AI risk today
                    </h2>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem', lineHeight: 1.7 }}>
                        Join PE firms and operators using sc0red Advisory to identify AI threats and build
                        defensible, AI-native business strategies.
                    </p>
                    <Link
                        href="/signup"
                        className="btn btn-primary btn-lg"
                        style={{ display: 'inline-flex' }}
                    >
                        Get Started — It&apos;s Free
                    </Link>
                </div>
            </section>

            {/* Footer */}
            <footer
                style={{ padding: '2rem', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}
            >
                <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
                    © 2026 sc0red Advisory · AI Risk & Strategic Intelligence
                </p>
            </footer>

            <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
        </div>
    )
}
