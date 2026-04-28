'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'

import RelativeTime from '@/components/ui/RelativeTime'
import { useActivityPolling } from '@/lib/hooks/useActivityPolling'
import type { ActivityEvent } from '@/lib/types/api'

const LAST_VIEWED_KEY = 'janus-activity-last-viewed'

interface ActivityPanelProps {
    /**
     * Optional initial last-viewed value. Tests pass `null` to start with
     * "everything is unread"; production reads from localStorage at mount.
     * Default: read from localStorage.
     */
    initialLastViewed?: string | null
}

/**
 * Bell-icon button + slide-out panel hosting the org-level activity feed.
 *
 * The bell sits in the sidebar nav; clicking it opens a fixed-position
 * panel above the layout. The panel is dismissed by clicking outside,
 * pressing Escape, or clicking the close button. While the panel is open,
 * the unread badge clears (last-viewed timestamp updates to "now") and
 * persists to localStorage so subsequent sessions only show events newer
 * than the last open.
 *
 * Polling cadence is 30s — see `useActivityPolling`. Polling runs whether
 * the panel is open or closed so the badge stays current.
 *
 * See `webapp-ux-foundations-tier2` §5.
 */
export default function ActivityPanel({ initialLastViewed }: ActivityPanelProps = {}) {
    const { events, loading } = useActivityPolling()
    const [isOpen, setIsOpen] = useState(false)
    const [lastViewed, setLastViewed] = useState<string | null>(() => {
        if (initialLastViewed !== undefined) return initialLastViewed
        if (typeof window === 'undefined') return null
        try {
            return window.localStorage.getItem(LAST_VIEWED_KEY)
        } catch {
            // Quota exceeded or storage disabled — treat as no prior view.
            return null
        }
    })
    const wrapperRef = useRef<HTMLDivElement>(null)

    const unreadCount = useMemo(() => {
        if (!lastViewed) return events.length
        return events.filter((event) => event.timestamp > lastViewed).length
    }, [events, lastViewed])

    function markRead() {
        const now = new Date().toISOString()
        setLastViewed(now)
        try {
            window.localStorage.setItem(LAST_VIEWED_KEY, now)
        } catch {
            // localStorage unavailable — badge stays in-memory until reload.
        }
    }

    function openPanel() {
        setIsOpen(true)
        markRead()
    }

    // Dismiss handlers — Escape + outside-click. Mirrors the HelpTooltip
    // pattern from §2 (always-mounted DOM, conditionally visible) so the
    // panel can carry a slide animation on `data-state` toggles.
    useEffect(() => {
        if (!isOpen) return
        const handleKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setIsOpen(false)
        }
        const handlePointer = (event: PointerEvent) => {
            if (!wrapperRef.current) return
            if (!wrapperRef.current.contains(event.target as Node)) setIsOpen(false)
        }
        document.addEventListener('keydown', handleKey)
        document.addEventListener('pointerdown', handlePointer)
        return () => {
            document.removeEventListener('keydown', handleKey)
            document.removeEventListener('pointerdown', handlePointer)
        }
    }, [isOpen])

    const showBadge = unreadCount > 0
    const badgeLabel = unreadCount > 99 ? '99+' : String(unreadCount)

    return (
        <div ref={wrapperRef} className="activity-panel-root">
            <button
                type="button"
                onClick={isOpen ? () => setIsOpen(false) : openPanel}
                className="activity-panel-trigger"
                aria-label={showBadge ? `Activity (${unreadCount} unread)` : 'Activity'}
                aria-expanded={isOpen}
                aria-haspopup="dialog"
            >
                <BellIcon />
                {showBadge && (
                    <span className="activity-panel-badge" aria-hidden="true">
                        {badgeLabel}
                    </span>
                )}
            </button>

            <div
                role="dialog"
                aria-label="Activity feed"
                className="activity-panel-popover"
                data-state={isOpen ? 'open' : 'closed'}
                aria-hidden={!isOpen}
            >
                <header className="activity-panel-header">
                    <span className="activity-panel-heading">Activity</span>
                    <button
                        type="button"
                        onClick={() => setIsOpen(false)}
                        className="activity-panel-close"
                        aria-label="Close activity panel"
                    >
                        <CloseIcon />
                    </button>
                </header>

                <div className="activity-panel-list" role="list">
                    {loading && events.length === 0 && (
                        <div className="activity-panel-empty">Loading activity…</div>
                    )}
                    {!loading && events.length === 0 && (
                        <div className="activity-panel-empty">
                            No activity yet. Run a scan or invite a teammate to see events here.
                        </div>
                    )}
                    {events.map((event) => (
                        <EventRow
                            key={event.id}
                            event={event}
                            isUnread={!lastViewed || event.timestamp > lastViewed}
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}

interface EventRowProps {
    event: ActivityEvent
    isUnread: boolean
}

function EventRow({ event, isUnread }: EventRowProps) {
    const targetHref = buildTargetHref(event)
    const content = (
        <div className="activity-panel-event" data-unread={isUnread} role="listitem">
            <div className="activity-panel-event-summary">{event.summary}</div>
            <div className="activity-panel-event-time">
                <RelativeTime value={event.timestamp} />
            </div>
        </div>
    )
    if (targetHref) {
        return (
            <Link href={targetHref} className="activity-panel-event-link">
                {content}
            </Link>
        )
    }
    return content
}

/**
 * Map an event to a navigable target. Events whose target doesn't have a
 * dedicated page (member events) render as plain rows.
 */
function buildTargetHref(event: ActivityEvent): string | null {
    switch (event.type) {
        case 'scan_started':
            return `/portfolio/${event.target.id}`
        case 'analysis_completed':
            return `/analysis/${event.target.id}`
        case 'member_invited':
        case 'member_joined':
            return '/team'
        default:
            return null
    }
}

function BellIcon() {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
            <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
    )
}

function CloseIcon() {
    return (
        <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
    )
}
