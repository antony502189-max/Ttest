import {
  CalendarDays,
  CigaretteOff,
  Euro,
  FileText,
  House,
  PawPrint,
  ShieldCheck,
  UserRound,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'

type ConditionTone = 'restriction' | 'neutral' | 'positive'

function conditionAppearance(value: string): { Icon: LucideIcon; tone: ConditionTone; wide: boolean } {
  const text = value.toLocaleLowerCase('es-ES')
  if (text.startsWith('habitación para')) return { Icon: House, tone: 'neutral', wide: false }
  if (text.startsWith('estancia mínima')) return { Icon: CalendarDays, tone: 'neutral', wide: true }
  if (text.includes('gastos')) return { Icon: Euro, tone: text.includes('incluid') ? 'positive' : 'neutral', wide: true }
  if (text.includes('mascota')) return { Icon: PawPrint, tone: text.startsWith('sin') ? 'restriction' : 'positive', wide: false }
  if (text.includes('fumar')) return { Icon: CigaretteOff, tone: text.includes('no fumar') ? 'restriction' : 'positive', wide: false }
  if (text.includes('niños')) return { Icon: UsersRound, tone: text.startsWith('sin') ? 'restriction' : 'positive', wide: false }
  if (text.includes('empadronamiento')) return { Icon: FileText, tone: text.startsWith('sin') ? 'restriction' : 'positive', wide: false }
  if (text.includes('hombre') || text.includes('mujer') || text.includes('persona')) {
    return { Icon: UserRound, tone: text.startsWith('solo') ? 'restriction' : 'neutral', wide: false }
  }
  return {
    Icon: ShieldCheck,
    tone: /\b(sin|solo|no)\b/.test(text) ? 'restriction' : /permitid|posible|incluid/.test(text) ? 'positive' : 'neutral',
    wide: false,
  }
}

/** Informational listing facts, not interactive buttons or search filters. */
export function ListingConditionChips({ conditions }: { conditions: string[] }) {
  return (
    <ul className="listing-conditions" aria-label="Condiciones del anuncio" data-testid="listing-conditions">
      {conditions.map((condition) => {
        const { Icon, tone, wide } = conditionAppearance(condition)
        return (
          <li
            key={condition}
            className={`listing-condition-chip listing-condition-chip--${tone}${wide ? ' listing-condition-chip--wide' : ''}`}
          >
            <Icon aria-hidden="true" />
            <span>{condition}</span>
          </li>
        )
      })}
    </ul>
  )
}
