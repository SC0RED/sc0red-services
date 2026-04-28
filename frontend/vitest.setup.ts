import '@testing-library/jest-dom'
import { vi } from 'vitest'

// jsdom doesn't ship ResizeObserver; cmdk and recharts both require it.
// Provide a no-op stub so any component test that mounts cmdk's Command
// or a Recharts ResponsiveContainer doesn't crash. Individual tests can
// still override with vi.stubGlobal if they need real behaviour.
if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn(),
    }))
}

// jsdom also lacks Element.prototype.scrollIntoView — cmdk uses it to
// keep the highlighted item visible inside the palette list.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn()
}

// jsdom's `localStorage` shim in this vitest version is missing
// `getItem` / `setItem` / `removeItem` / `clear`. The activity panel
// (Tier 2 §5) persists "last viewed" to localStorage; without a real
// stub the test file can't exercise it.
if (typeof window !== 'undefined') {
    const needsStub =
        typeof window.localStorage === 'undefined' || typeof window.localStorage.getItem !== 'function'
    if (needsStub) {
        const storage = new Map<string, string>()
        Object.defineProperty(window, 'localStorage', {
            configurable: true,
            value: {
                getItem: (key: string) => storage.get(key) ?? null,
                setItem: (key: string, value: string) => {
                    storage.set(key, value)
                },
                removeItem: (key: string) => {
                    storage.delete(key)
                },
                clear: () => {
                    storage.clear()
                },
                key: (index: number) => Array.from(storage.keys())[index] ?? null,
                get length() {
                    return storage.size
                },
            },
        })
    }
}
