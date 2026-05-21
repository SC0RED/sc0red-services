/**
 * Shared string-manipulation helpers. Lives here (not inline in
 * components) so that any locale-aware or edge-case fix lands in one
 * place — per CLAUDE.md cross-file-duplication rule.
 */

/**
 * Uppercase the first character of `value`, leaving the rest unchanged.
 *
 * Intentionally simple — does NOT handle locale-aware casing (Turkish
 * dotted/dotless I, German eszett, etc). The current callers operate
 * on already-known ASCII enum values (e.g. `confidence.toLowerCase()`
 * yielding "high" / "medium" / "low") where locale-aware handling
 * would be over-engineering. If a caller ever needs locale handling,
 * upgrade this helper rather than inlining a parallel implementation.
 *
 * @example capitalise('high') // "High"
 * @example capitalise('')     // ""
 */
export function capitalise(value: string): string {
    if (value.length === 0) return value
    return value.charAt(0).toUpperCase() + value.slice(1)
}

/**
 * Truncate `text` to at most `maxChars` characters, appending an
 * ellipsis (`…`) when the input exceeds the budget. The ellipsis
 * counts toward the budget, so the visible cut is `maxChars - 1`
 * characters of the input. Trailing whitespace is trimmed before the
 * ellipsis so the output never looks like `"prefix …"`.
 *
 * Intentionally simple — does NOT respect word boundaries, locale-
 * aware grapheme clusters, or right-to-left scripts. Current callers
 * (e.g. the Quick Wins matrix inline dot label) operate on English
 * AI-generated opportunity titles where a hard character cut is
 * acceptable. If a caller ever needs word-aware truncation, upgrade
 * this helper rather than inlining a parallel implementation.
 *
 * Empty input or `maxChars <= 0` returns the original string
 * unchanged so callers don't need to defensive-check.
 *
 * @example truncate('Deploy AI churn prediction model', 22) // "Deploy AI churn predi…"
 * @example truncate('Short', 22) // "Short"
 */
export function truncate(text: string, maxChars: number): string {
    if (maxChars <= 0 || text.length <= maxChars) return text
    return `${text.slice(0, maxChars - 1).trimEnd()}…`
}
