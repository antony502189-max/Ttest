// Guest-only pilot. No marketplace provider, account hydration or startup IO.
export function useApp(): { currentUser: { id: string } | null } { return { currentUser: null } }
