import type { AIIntent } from '@/api/ai-intent'
import { aiConditionRows } from '@/api/ai-intent'
import { useI18n } from '@/contexts/i18n-context'

export function AIConditions({ intent, title }: { intent: AIIntent; title: string }) {
  const { t } = useI18n()
  const rows = aiConditionRows(intent, t)
  return <section className="ai-conditions" aria-label={t(title)}>
    <h3>{t(title)}</h3>
    {rows === null ? <p role="alert">{t('No podemos mostrar todas las condiciones de esta versión de búsqueda.')}</p>
      : rows.length === 0 ? <p>{t('Sin condiciones seleccionadas.')}</p>
        : (['hard', 'soft'] as const).map(strength => {
          const group = rows.filter(row => row.strength === strength)
          return group.length ? <div key={strength}><h4>{t(strength === 'hard' ? 'Requisitos obligatorios' : 'Preferencias')}</h4>
            <dl>{group.map(row => <div key={row.name}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl></div> : null
        })}
  </section>
}
