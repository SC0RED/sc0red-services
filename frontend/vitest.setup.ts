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
