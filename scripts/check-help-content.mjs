#!/usr/bin/env node
/**
 * Verify that `frontend/src/lib/help-content.ts` and
 * `docs/help-content.md` agree on title + body for every term.
 *
 * The TS file is the source of truth (it's what the app renders); the
 * markdown exists for non-engineering review and is the file that gets
 * edited first when copy changes. This script enforces sync — running
 * it in CI on every PR catches the "edited the markdown, forgot the
 * code" failure mode.
 *
 * Run: `node scripts/check-help-content.mjs` (from repo root).
 * Exits non-zero on mismatch with a clear diff.
 */

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const TS_PATH = path.join(ROOT, 'frontend/src/lib/help-content.ts')
const MD_PATH = path.join(ROOT, 'docs/help-content.md')

/**
 * Parse the TS registry. Format:
 *
 *     key_name: {
 *         title: 'Title',
 *         body: "Body. Possibly with 'apostrophes' or escapes.",
 *     },
 *
 * Returns: Map<string, { title: string, body: string }>.
 *
 * **Authoring constraints** (enforced implicitly by this regex):
 *   - `title` and `body` MUST be ordinary string literals — single OR
 *     double quoted (prettier picks the form that minimises escaping).
 *     Template literals (`` ` ``) are NOT parsed. The
 *     `tsEntries.size === 0` guard catches wholesale format changes;
 *     a single rogue entry surfaces as `"Missing in TS"` from the diff.
 *   - Quotes of the same kind as the surrounding delimiter must be
 *     backslash-escaped. Mixing fine: `"don't"` parses; `'don\'t'`
 *     parses; `'don't'` does not.
 *
 * The codegen-style of this file is hand-edited so these constraints
 * are easy to keep. If the format ever needs richer content
 * (multi-paragraph bodies, embedded markdown), replace this regex
 * parser with a real TS AST walk via `typescript` or `tsx`.
 */
function parseTs(source) {
    // Match either form: 'string with \'escapes\'' or "string with 'apostrophes'".
    const STRING = `(?:'((?:[^'\\\\]|\\\\.)*)'|"((?:[^"\\\\]|\\\\.)*)")`
    const entryRegex = new RegExp(
        `(\\w+):\\s*\\{\\s*title:\\s*${STRING},\\s*body:\\s*${STRING},?\\s*\\}`,
        'g'
    )
    const entries = new Map()
    let match
    while ((match = entryRegex.exec(source)) !== null) {
        const [, key, titleSingle, titleDouble, bodySingle, bodyDouble] = match
        const title = titleSingle ?? titleDouble ?? ''
        const body = bodySingle ?? bodyDouble ?? ''
        entries.set(key, { title: unescape(title), body: unescape(body) })
    }
    return entries
}

/**
 * Parse the markdown mirror. Format:
 *
 *     ### `key_name` — Title
 *
 *     Body.
 *
 * Returns: Map<string, { title: string, body: string }>.
 */
function parseMd(source) {
    // Match each section: ### `key` — Title\n\nbody-paragraph
    const sectionRegex = /^### `([^`]+)` — ([^\n]+)\n\n([^\n]+)\n?/gm
    const entries = new Map()
    let match
    while ((match = sectionRegex.exec(source)) !== null) {
        const [, key, title, body] = match
        entries.set(key, { title: title.trim(), body: body.trim() })
    }
    return entries
}

function unescape(s) {
    return s.replace(/\\'/g, "'").replace(/\\\\/g, '\\')
}

function diff(tsEntries, mdEntries) {
    const errors = []
    const tsKeys = new Set(tsEntries.keys())
    const mdKeys = new Set(mdEntries.keys())

    for (const key of tsKeys) {
        if (!mdKeys.has(key)) {
            errors.push(`Missing in docs/help-content.md: \`${key}\``)
        }
    }
    for (const key of mdKeys) {
        if (!tsKeys.has(key)) {
            errors.push(`Missing in frontend/src/lib/help-content.ts: \`${key}\``)
        }
    }
    for (const key of tsKeys) {
        if (!mdKeys.has(key)) continue
        const ts = tsEntries.get(key)
        const md = mdEntries.get(key)
        if (ts.title !== md.title) {
            errors.push(
                `Title mismatch for \`${key}\`:\n  TS:  ${ts.title}\n  MD:  ${md.title}`
            )
        }
        if (ts.body !== md.body) {
            errors.push(
                `Body mismatch for \`${key}\`:\n  TS:  ${ts.body}\n  MD:  ${md.body}`
            )
        }
    }
    return errors
}

function main() {
    const tsSource = readFileSync(TS_PATH, 'utf8')
    const mdSource = readFileSync(MD_PATH, 'utf8')

    const tsEntries = parseTs(tsSource)
    const mdEntries = parseMd(mdSource)

    if (tsEntries.size === 0) {
        console.error(`✘ No entries parsed from ${TS_PATH}. Has the file format changed?`)
        process.exit(2)
    }
    if (mdEntries.size === 0) {
        console.error(`✘ No entries parsed from ${MD_PATH}. Has the file format changed?`)
        process.exit(2)
    }

    const errors = diff(tsEntries, mdEntries)
    if (errors.length > 0) {
        console.error('✘ help-content drift detected:')
        for (const error of errors) {
            console.error('  ' + error.replace(/\n/g, '\n  '))
        }
        process.exit(1)
    }

    console.log(`✓ help-content.ts and help-content.md agree (${tsEntries.size} terms).`)
}

main()
