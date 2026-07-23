import { redirect } from 'next/navigation'

/** Connected Apps folded into the top-level Connect page. Redirect old links. */
export default function ConnectedAppsRedirect() {
    redirect('/connect')
}
