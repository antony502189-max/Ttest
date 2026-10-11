import type { AdminAccount, AdminAuditLog, AdminListing, AdminUser, HomepageHeroPromotion } from '@/api/admin'
import type { AdminReport } from '@/api/reports'

export type AdminTab = 'users' | 'reports' | 'listings' | 'advertisements' | 'activity' | 'settings'

export type AdminTabSources = {
  users: () => Promise<AdminUser[]>
  listings: () => Promise<AdminListing[]>
  homepageHero: () => Promise<HomepageHeroPromotion | null>
  reports: () => Promise<AdminReport[]>
  activity: () => Promise<AdminAuditLog[]>
  settings: () => Promise<AdminAccount[]>
}

export type AdminTabResult =
  | { tab: 'users'; users: AdminUser[] }
  | { tab: 'listings'; listings: AdminListing[]; homepageHero: HomepageHeroPromotion | null }
  | { tab: 'reports'; reports: AdminReport[] }
  | { tab: 'activity'; audit: AdminAuditLog[] }
  | { tab: 'settings'; admins: AdminAccount[] }

/**
 * Load precisely the requested admin tab. Keeping unrelated calls out of the
 * visible Users load avoids waiting for full listing/audit pagination. The
 * caller owns cache, errors and retry and applies each tab's data separately.
 */
export async function fetchAdminTab(tab: AdminTab, sources: AdminTabSources): Promise<AdminTabResult | null> {
  switch (tab) {
    case 'users':
      return { tab, users: await sources.users() }
    case 'listings': {
      const [listings, homepageHero] = await Promise.all([sources.listings(), sources.homepageHero()])
      return { tab, listings, homepageHero }
    }
    case 'reports':
      return { tab, reports: await sources.reports() }
    case 'activity':
      return { tab, audit: await sources.activity() }
    case 'settings':
      return { tab, admins: await sources.settings() }
    case 'advertisements':
      return null // This tab renders its own client and pagination.
  }
}
