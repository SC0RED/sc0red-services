import { afterEach, describe, expect, it } from 'vitest'

import { SC0RED_CONTACT_URL_DEFAULT, getSc0redContactUrl } from '@/lib/config'

describe('getSc0redContactUrl', () => {
    const originalValue = process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL

    afterEach(() => {
        if (originalValue === undefined) {
            delete process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL
        } else {
            process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL = originalValue
        }
    })

    it('returns the default URL when the env var is unset', () => {
        delete process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL
        expect(getSc0redContactUrl()).toBe(SC0RED_CONTACT_URL_DEFAULT)
    })

    it('returns the env var when it is set to a non-empty value', () => {
        process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL = 'https://calendly.com/sc0red'
        expect(getSc0redContactUrl()).toBe('https://calendly.com/sc0red')
    })

    it('treats an empty string as unset and returns the default', () => {
        process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL = ''
        expect(getSc0redContactUrl()).toBe(SC0RED_CONTACT_URL_DEFAULT)
    })

    it('treats whitespace-only value as unset and returns the default', () => {
        process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL = '   '
        expect(getSc0redContactUrl()).toBe(SC0RED_CONTACT_URL_DEFAULT)
    })

    it('uses https://www.sc0red.com/contact as the hardcoded default', () => {
        expect(SC0RED_CONTACT_URL_DEFAULT).toBe('https://www.sc0red.com/contact')
    })
})
