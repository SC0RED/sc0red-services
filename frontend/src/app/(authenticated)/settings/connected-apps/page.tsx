import { redirect } from 'next/navigation'

/**
 * The Connected Apps page was folded into the self-serve Connect page
 * (address -> set it up -> manage). Redirect any old links/bookmarks there.
 */
export default function ConnectedAppsRedirect() {
    redirect('/settings/connect')
}
