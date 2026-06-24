import { useCallback, useRef, useState } from 'react'

import type { Company } from '@/lib/types/scan'
import { hasAnalyzableUrl } from '@/lib/types/scan'

interface IncomingCompany {
    name: string
    url: string
}

interface UseCompanyList {
    companies: Company[]
    /** Replace the whole list (e.g. when discovery completes). */
    replace: (companies: Company[]) => void
    toggle: (index: number, selected: boolean) => void
    addOne: (name: string, url: string) => void
    /** Bulk-merge, deduping by URL (when present) and case-insensitive name.
     *  Returns the number of companies actually added. */
    addMany: (incoming: IncomingCompany[]) => number
}

/**
 * Owns the editable confirmation list. A ref mirrors the state so the
 * merge/toggle helpers always read the current list synchronously — this
 * avoids a stale-closure race where a file upload resolving mid-edit would
 * dedup against an outdated snapshot and duplicate rows.
 */
export function useCompanyList(): UseCompanyList {
    const [companies, setCompanies] = useState<Company[]>([])
    const ref = useRef<Company[]>([])

    const commit = useCallback((next: Company[]) => {
        ref.current = next
        setCompanies(next)
    }, [])

    const replace = useCallback((next: Company[]) => commit(next), [commit])

    const toggle = useCallback(
        (index: number, selected: boolean) => {
            commit(ref.current.map((company, i) => (i === index ? { ...company, selected } : company)))
        },
        [commit]
    )

    const addOne = useCallback(
        (name: string, url: string) => {
            commit([...ref.current, { name, url, description: '', selected: true, source: 'upload' }])
        },
        [commit]
    )

    const addMany = useCallback(
        (incoming: IncomingCompany[]) => {
            const existingUrls = new Set(ref.current.map((c) => c.url).filter(Boolean))
            const existingNames = new Set(ref.current.map((c) => c.name.toLowerCase()))
            const fresh: Company[] = []
            for (const company of incoming) {
                const duplicate =
                    (company.url && existingUrls.has(company.url)) ||
                    existingNames.has(company.name.toLowerCase())
                if (duplicate) continue
                fresh.push({
                    name: company.name,
                    url: company.url,
                    description: '',
                    // Only pre-select if analyzable — a url-less upload row must
                    // not be counted/confirmed, or it's silently dropped at confirm.
                    selected: hasAnalyzableUrl(company.url),
                    source: 'upload',
                })
                if (company.url) existingUrls.add(company.url)
                existingNames.add(company.name.toLowerCase())
            }
            if (fresh.length > 0) commit([...ref.current, ...fresh])
            return fresh.length
        },
        [commit]
    )

    return { companies, replace, toggle, addOne, addMany }
}
