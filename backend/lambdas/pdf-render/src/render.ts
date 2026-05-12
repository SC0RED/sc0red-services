/**
 * Puppeteer orchestration: launch headless Chromium, navigate to the
 * print route, snapshot the rendered tree as a PDF.
 *
 * Implements `decision D4` from the design (A4, 25mm margins, 30mm on
 * the cover; header/footer templates with company name + page numbers).
 * No business logic here — the only inputs are an analysisId + token,
 * the only output is a PDF buffer.
 */

import chromium from '@sparticuz/chromium'
import puppeteer, { type Browser, type Page, type PDFOptions } from 'puppeteer-core'

export interface RenderOptions {
    /** The print URL to navigate to, e.g. `https://app.example/print/{id}?t=...`. */
    printUrl: string
    /** Company name — used in the running header template. */
    companyName: string
    /**
     * Maximum time the navigation + render is allowed to take, in ms.
     * Defaults to 25_000 so the Lambda's 30s timeout has 5s of headroom
     * for cold-start init + buffer-to-API-Gateway overhead.
     */
    timeoutMs?: number
}

export interface RenderMetrics {
    durationMs: number
    pageCount: number
    pdfSizeBytes: number
}

export interface RenderResult {
    pdf: Buffer
    metrics: RenderMetrics
}

/**
 * Discriminated failure for the print-page status check. The print route
 * emits `<meta name="x-print-status">` indicating whether the rendered tree
 * is the real analysis (`ok`) or a server-component-rendered error page
 * (`unauthorized` / `not_found`). Without this check, an "Unauthorized"
 * page would render as a successful 200 PDF — see review-fixes PR.
 */
export class PrintStatusError extends Error {
    constructor(public readonly status: string) {
        super(`Print page reported status: ${status}`)
        this.name = 'PrintStatusError'
    }
}

const DEFAULT_TIMEOUT_MS = 25_000

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
}

function buildPdfOptions(companyName: string): PDFOptions {
    const safeCompany = escapeHtml(companyName)
    return {
        format: 'A4',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate: `<div style="font-size:8pt;color:#475569;width:100%;text-align:center;padding:0 12mm;">
            ${safeCompany} — AI Risk Report
        </div>`,
        footerTemplate: `<div style="font-size:8pt;color:#475569;width:100%;text-align:center;padding:0 12mm;">
            Page <span class="pageNumber"></span> of <span class="totalPages"></span> · sc0red.com
        </div>`,
        margin: { top: '25mm', bottom: '25mm', left: '20mm', right: '20mm' },
    }
}

/**
 * Launch a fresh Chromium instance, navigate, render, return.
 * The browser is closed even on error — leaking processes in the Lambda
 * runtime fills `/tmp` and bricks subsequent invocations on the same
 * container.
 */
export async function renderPdf(options: RenderOptions): Promise<RenderResult> {
    const start = Date.now()
    const timeout = options.timeoutMs ?? DEFAULT_TIMEOUT_MS

    let browser: Browser | undefined
    try {
        browser = await puppeteer.launch({
            args: chromium.args,
            defaultViewport: chromium.defaultViewport,
            executablePath: await chromium.executablePath(),
            headless: chromium.headless,
        })

        const page = await browser.newPage()
        // `networkidle0` waits until there are 0 in-flight requests for 500ms,
        // which covers the print route's data fetch + chart render. The
        // Recharts SVGs and ReactFlow EBITDA tree fall into this window
        // naturally because they finish layout in the same tick.
        await page.goto(options.printUrl, { waitUntil: 'networkidle0', timeout })

        // Sanity-check the page actually rendered the analysis. Without this,
        // a server-component-rendered "Unauthorized" page (which Next.js
        // returns as a 200) would silently produce a successful PDF of the
        // error message. The print route stamps a `<meta name="x-print-status">`
        // marker on every render path; we require it to be `ok` before
        // calling `page.pdf()`. See `frontend/src/app/print/[analysisId]/page.tsx`.
        await verifyPrintStatus(page)

        const pdf = await page.pdf(buildPdfOptions(options.companyName))

        // Grab the page count off Puppeteer's PDF — we don't have a direct
        // API, so estimate from the buffer's `/Count` PDF directive. Cheap
        // and good enough for capacity logging; not relied on for billing.
        const pdfBuffer = pdf as unknown as Buffer
        const pageCount = countPdfPages(pdfBuffer)

        return {
            pdf: pdfBuffer,
            metrics: {
                durationMs: Date.now() - start,
                pageCount,
                pdfSizeBytes: pdfBuffer.length,
            },
        }
    } finally {
        if (browser) {
            try {
                // Do NOT `await browser.close()` — it can hang up to 30+
                // seconds on pages with lingering connections (Next.js
                // hydration, font loaders, analytics beacons). The
                // `durationMs` metric is captured at the return-value
                // evaluation above, but the handler's `totalDurationMs`
                // includes this finally block — so a slow close pushes
                // the Lambda past API Gateway's hard 29s integration
                // timeout. Observed: 70s total handler time on an 8-page
                // PDF whose `page.pdf()` itself takes ~15s.
                //
                // SIGKILL is fine: the response is already prepared, and
                // the Lambda container's /tmp gets reclaimed when the
                // container is recycled. We do NOT leak processes across
                // invocations because Lambda owns the container lifecycle.
                const proc = browser.process()
                if (proc && !proc.killed) proc.kill('SIGKILL')
            } catch {
                // Already gone — ignore. The original error (if any)
                // has already propagated up the try; we don't want to
                // mask it with a close-time failure.
            }
        }
    }
}

/**
 * Read the `<meta name="x-print-status">` marker the print route emits.
 * Throws `PrintStatusError` if the marker is missing (page didn't render
 * at all, or rendered a non-print page) or has any value other than `ok`
 * (auth failure, not-found, etc.).
 *
 * The print route ALWAYS emits the marker on every code path — the `ok`
 * branch from the success render, `unauthorized` / `not_found` from
 * `UnauthorizedView`. A missing marker means something rendered that we
 * didn't author (proxy error page, framework default, etc.); fail loudly.
 */
async function verifyPrintStatus(page: Page): Promise<void> {
    const status = await page
        .$eval('meta[name="x-print-status"]', (element) => element.getAttribute('content'))
        .catch(() => null)
    if (status === 'ok') return
    throw new PrintStatusError(status ?? 'missing_marker')
}

/**
 * Cheap page-count estimate from a PDF buffer. Looks for the `/Count` directive
 * in the page-tree dictionary. If parsing fails (corrupt PDF, weird structure)
 * returns 1 — better to under-count for capacity logs than to crash.
 */
function countPdfPages(pdf: Buffer): number {
    try {
        const ascii = pdf.toString('latin1')
        const match = ascii.match(/\/Type\s*\/Pages[^/]*\/Count\s+(\d+)/)
        if (match) return Number.parseInt(match[1], 10)
        // Fallback: count `/Type /Page` minus 1 for the catalog. Rough.
        const pageMatches = ascii.match(/\/Type\s*\/Page[^s]/g)
        return pageMatches ? pageMatches.length : 1
    } catch {
        return 1
    }
}
