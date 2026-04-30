'use client'

import { Monitor, Moon, Sun } from 'lucide-react'

import { type ThemeMode, useTheme } from '@/lib/hooks/useTheme'

interface Option {
    value: ThemeMode
    label: string
    description: string
    icon: typeof Sun
}

const OPTIONS: readonly Option[] = [
    { value: 'dark', label: 'Dark', description: 'Always dark', icon: Moon },
    { value: 'light', label: 'Light', description: 'Always light', icon: Sun },
    { value: 'system', label: 'System', description: 'Follow OS preference', icon: Monitor },
]

/**
 * Three-option theme picker (Dark / Light / System) for the Settings page.
 * Reads + writes via {@link useTheme}.
 *
 * Rendered as a real `<input type="radio">` group — keyboard navigation,
 * screen-reader semantics, and form-element behaviour come for free.
 */
export default function ThemeToggle() {
    const { mode, setTheme } = useTheme()
    return (
        <div role="radiogroup" aria-label="Theme preference" style={{ display: 'grid', gap: '0.5rem' }}>
            {OPTIONS.map((option) => {
                const checked = mode === option.value
                const Icon = option.icon
                return (
                    <label
                        key={option.value}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem',
                            padding: '0.75rem 1rem',
                            borderRadius: 'var(--radius-md)',
                            border: checked
                                ? '1px solid var(--accent-blue)'
                                : '1px solid var(--border-subtle)',
                            background: checked ? 'var(--accent-blue-glow)' : 'transparent',
                            cursor: 'pointer',
                            transition:
                                'border-color var(--transition-fast), background var(--transition-fast)',
                        }}
                    >
                        <input
                            type="radio"
                            name="theme"
                            value={option.value}
                            checked={checked}
                            onChange={() => setTheme(option.value)}
                            style={{ accentColor: 'var(--accent-blue)' }}
                        />
                        <Icon size={16} aria-hidden="true" style={{ color: 'var(--text-secondary)' }} />
                        <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                                {option.label}
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                                {option.description}
                            </div>
                        </div>
                    </label>
                )
            })}
        </div>
    )
}
