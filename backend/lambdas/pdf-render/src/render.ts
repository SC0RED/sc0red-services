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
import puppeteer, { type Browser, type PDFOptions } from 'puppeteer-core'

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
                await browser.close()
            } catch {
                // Browser was already gone (e.g. timeout killed it). Don't
                // mask the original error with a close-time failure.
            }
        }
    }
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
