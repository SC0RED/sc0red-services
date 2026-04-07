'use client'

import { useReportWebVitals } from 'next/web-vitals'

import { reportWebVital } from '@/lib/reportWebVitals'

export default function WebVitals() {
    useReportWebVitals(reportWebVital)
    return null
}
