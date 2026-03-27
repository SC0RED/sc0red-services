import { useState, useEffect, useRef, useCallback } from 'react'
import { usePathname } from 'next/navigation'

interface UseMobileMenuReturn {
    isOpen: boolean
    open: () => void
    close: () => void
    hamburgerRef: React.RefObject<HTMLButtonElement>
    closeRef: React.RefObject<HTMLButtonElement>
}

export function useMobileMenu(): UseMobileMenuReturn {
    const pathname = usePathname()
    const [isOpen, setIsOpen] = useState(false)
    const hamburgerRef = useRef<HTMLButtonElement>(null)
    const closeRef = useRef<HTMLButtonElement>(null)

    const close = useCallback(() => {
        setIsOpen(false)
        hamburgerRef.current?.focus()
    }, [])

    const open = useCallback(() => {
        setIsOpen(true)
    }, [])

    // Close on navigation
    useEffect(() => {
        setIsOpen(false)
    }, [pathname])

    // Scroll lock + focus management
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden'
            closeRef.current?.focus()
        } else {
            document.body.style.overflow = ''
        }
        return () => {
            document.body.style.overflow = ''
        }
    }, [isOpen])

    // Escape key dismiss
    useEffect(() => {
        if (!isOpen) return
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') close()
        }
        document.addEventListener('keydown', handleEscape)
        return () => document.removeEventListener('keydown', handleEscape)
    }, [isOpen, close])

    return { isOpen, open, close, hamburgerRef, closeRef }
}
