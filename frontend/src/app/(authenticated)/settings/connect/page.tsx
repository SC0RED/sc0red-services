import { redirect } from 'next/navigation'

/** Connect moved to the top-level /connect nav item. Redirect old links. */
export default function SettingsConnectRedirect() {
    redirect('/connect')
}
