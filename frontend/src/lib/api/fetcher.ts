/**
 * Shared fetcher for SWR — handles JSON responses and error extraction.
 */
export async function fetcher<T = unknown>(url: string): Promise<T> {
    const response = await fetch(url)

    if (!response.ok) {
        let message = `Request failed: ${response.status}`
        try {
            const body = (await response.json()) as { error?: string }
            message = body.error ?? message
        } catch {
            // Response body is not JSON
        }
        throw new Error(message)
    }

    return response.json() as Promise<T>
}
