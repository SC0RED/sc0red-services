'use client'

import { useState } from 'react'

import { useToast } from '@/components/ui'

/**
 * Section ② of the Connect page — per-client setup instructions. Claude Desktop
 * and Cursor get full walkthroughs with copy-able config snippets templated on
 * the server address; ChatGPT gets a hedged pointer + link-out (its custom-MCP
 * support is beta, paid-plan-gated, and its UI path shifts — see the change's
 * design.md). URL-dependent snippets are hidden when the address is unavailable.
 */
const CHATGPT_DEVELOPER_MODE_GUIDE =
    'https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt'

type ClientTab = 'claude' | 'cursor' | 'chatgpt'

const TABS: { id: ClientTab; label: string }[] = [
    { id: 'claude', label: 'Claude Desktop' },
    { id: 'cursor', label: 'Cursor & others' },
    { id: 'chatgpt', label: 'ChatGPT' },
]

export default function ClientSetup({ url, available }: { url: string; available: boolean }) {
    const [tab, setTab] = useState<ClientTab>('claude')

    return (
        <section className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <h2 style={SECTION_HEADING}>Set it up in your assistant</h2>

            <div role="tablist" aria-label="AI assistant" style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                {TABS.map((t) => (
                    <button
                        key={t.id}
                        type="button"
                        role="tab"
                        aria-selected={tab === t.id}
                        onClick={() => setTab(t.id)}
                        className={tab === t.id ? 'btn btn-secondary btn-sm' : 'btn btn-ghost btn-sm'}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {tab === 'claude' && <ClaudeDesktop url={url} available={available} />}
            {tab === 'cursor' && <Cursor url={url} available={available} />}
            {tab === 'chatgpt' && <ChatGpt />}
        </section>
    )
}

function ClaudeDesktop({ url, available }: { url: string; available: boolean }) {
    return (
        <div>
            <ol style={STEPS}>
                <li>Open <strong>Settings → Connectors</strong> and choose <strong>Add custom connector</strong>.</li>
                <li>Paste the server address above.</li>
                <li>Sign in with sc0red on the popup and approve access.</li>
            </ol>
            {available && (
                <details style={{ marginTop: '1rem' }}>
                    <summary style={SUMMARY}>File-only setup (older clients, via the mcp-remote bridge — needs Node 18+)</summary>
                    <p style={NOTE}>Add this to <code>claude_desktop_config.json</code>:</p>
                    <CodeBlock
                        label="Claude Desktop config"
                        code={JSON.stringify(
                            { mcpServers: { 'sc0red-services': { command: 'npx', args: ['-y', 'mcp-remote', url] } } },
                            null,
                            2
                        )}
                    />
                </details>
            )}
        </div>
    )
}

function Cursor({ url, available }: { url: string; available: boolean }) {
    return (
        <div>
            <ol style={STEPS}>
                <li>Add a remote MCP server to <code>~/.cursor/mcp.json</code> (or <code>.cursor/mcp.json</code> in your project):</li>
            </ol>
            {available ? (
                <CodeBlock
                    label="Cursor mcp.json"
                    code={JSON.stringify({ mcpServers: { 'sc0red-services': { url } } }, null, 2)}
                />
            ) : (
                <p style={NOTE}>The config snippet will appear here once the server address is available.</p>
            )}
            <p style={NOTE}>Then sign in with sc0red the first time Cursor connects. Any MCP client that supports a remote (HTTP) server with OAuth can use the same address.</p>
        </div>
    )
}

function ChatGpt() {
    return (
        <p style={{ ...STEPS, paddingLeft: 0 }}>
            ChatGPT support is in beta and requires a paid plan. Enable <strong>Developer Mode</strong> in
            ChatGPT&rsquo;s settings, add the server address above, and sign in with sc0red. The exact menu
            location changes as the feature evolves — see{' '}
            <a href={CHATGPT_DEVELOPER_MODE_GUIDE} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                OpenAI&rsquo;s Developer Mode guide
            </a>
            .
        </p>
    )
}

function CodeBlock({ code, label }: { code: string; label: string }) {
    const toast = useToast()
    const [copied, setCopied] = useState(false)
    async function copy() {
        try {
            await navigator.clipboard.writeText(code)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch {
            toast.error('Could not copy to clipboard')
        }
    }
    return (
        <div style={{ position: 'relative', marginTop: '0.5rem' }}>
            <button
                type="button"
                onClick={copy}
                className="btn btn-ghost btn-sm"
                style={{ position: 'absolute', top: '0.4rem', right: '0.4rem' }}
                aria-label={`Copy ${label}`}
            >
                {copied ? 'Copied' : 'Copy'}
            </button>
            <pre
                style={{
                    margin: 0,
                    padding: '0.75rem',
                    background: 'var(--surface-sunken)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.8125rem',
                    overflowX: 'auto',
                }}
            >
                <code>{code}</code>
            </pre>
        </div>
    )
}

const SECTION_HEADING = {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    marginBottom: '0.75rem',
}
const STEPS = { margin: 0, paddingLeft: '1.25rem', color: 'var(--text-secondary)', fontSize: '0.9375rem', lineHeight: 1.7 }
const SUMMARY = { cursor: 'pointer', fontSize: '0.875rem', color: 'var(--text-secondary)' }
const NOTE = { marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }
