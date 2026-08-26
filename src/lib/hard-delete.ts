import type { DemoUser } from '@/types'

const HARD_DELETE_EMAILS = new Set(['antony502189@gmail.com', 'tf.shuler@gmail.com'])

/** UI affordance only; the API independently verifies this exact condition. */
export function canUseHardDelete(user: DemoUser | null): boolean {
  return Boolean(user?.emailVerified && HARD_DELETE_EMAILS.has(user.email.trim().toLowerCase()))
}
