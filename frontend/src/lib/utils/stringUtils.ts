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
