/**
 * Server-side analytics emit helper.
 *
 * Used by the Next.js PDF export route to log the `sc0red_cta_rendered_in_pdf`
 * event. Differs from the browser emit helper in that it calls the
 * Python backend directly via `backendFetch()` with a server-side ID
 * token — there is no browser in scope and no Next.js proxy route to
 * bounce through.
 *
 * Failures are logged but never re-thrown — a broken analytics sink
 * must not abort the PDF download.
 */

import { buildPdfEnvelope } from '@/lib/analytics/emitEvent'
import { backendFetch } from '@/lib/api/serverToken'
import type { PdfEventContext } from '@/lib/types/analytics'

export async function emitFromServer(
    _eventType: 'sc0red_cta_rendered_in_pdf',
    context: PdfEventContext
): Promise<void> {
    // The `_eventType` parameter exists to make the call site read
    // symmetrically with the browser `emit()` helper; its literal-string
    // type is all the narrowing we need. If a second server-side event
    // is added later, broaden the union AND switch-with-exhaustiveness
    // inside — don't add a runtime guard against the type system.
    const envelope = buildPdfEnvelope(context)
    try {
        await backendFetch('/api/analytics/events', {
            method: 'POST',
            body: envelope,
        })
    } catch (error) {
        // eslint-disable-next-line no-console
        console.warn(
            `[analytics] server emit failed for ${envelope.event_type}:`,
            error instanceof Error ? error.message : error
        )
    }
}
