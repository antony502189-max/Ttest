import { Bell, Heart, Home, Menu } from 'lucide-react'
import { useNavigate } from 'react-router'
import { useI18n } from '@/contexts/i18n-context'
import { cn } from '@/lib/utils'

export type MobileTab = 'home' | 'searches' | 'favorites' | 'menu'

const items = [
  { tab: 'home', to: '/', label: 'Inicio', icon: Home },
  { tab: 'searches', to: '/busquedas-guardadas', label: 'Búsquedas', icon: Bell },
  { tab: 'favorites', to: '/favoritos', label: 'Favoritos', icon: Heart },
  { tab: 'menu', to: '/menu', label: 'Menú', icon: Menu },
] as const

export function MobileBottomNavigation({ activeTab, fullWidth = false }: { activeTab: MobileTab; fullWidth?: boolean }) {
  const navigate = useNavigate()
  const { t } = useI18n()
  return <nav className={cn('m2-bottom-nav notranslate', fullWidth && 'm2-bottom-nav--full-width')} translate="no" aria-label={t('Navegación principal')}>
    {items.map(({ tab, to, label, icon: Icon }) => <button key={tab} type="button" className={cn(activeTab === tab && 'is-active')} aria-current={activeTab === tab ? 'page' : undefined} onClick={() => navigate(to)}><Icon /><span>{t(label)}</span></button>)}
  </nav>
}
