import { useMemo, useState, type FormEvent } from 'react'
import { Cigarette, CigaretteOff, PawPrint, Search } from 'lucide-react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { RentalTypeSwitch, SearchLocationInput } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { filtersToParams } from '@/lib/search'
import { resolveTenerifeLocation } from '@/lib/tenerife'
import {
  applyListingAccessProfile,
  hasListingAccessSelection,
  persistListingAccessProfile,
  readListingAccessProfile,
  type HomeOccupantChoice,
  type ListingAccessProfile,
} from '@/lib/listing-access'
import { cn } from '@/lib/utils'
import {
  occupantAnyIcon,
  occupantCoupleIcon,
  occupantFamilyIcon,
  occupantManIcon,
  occupantPersonIcon,
  occupantPetsIcon,
  occupantWomanIcon,
} from '@/assets/occupants'
import '@/home-mandatory-search.css'

const occupantOptions: Array<{ value: Exclude<HomeOccupantChoice, null>; label: string; iconSrc: string }> = [
  { value: 'single-person', label: '1 persona', iconSrc: occupantPersonIcon },
  { value: 'couple', label: '2 personas (pareja/amigos)', iconSrc: occupantCoupleIcon },
  { value: 'single-man', label: 'Solo hombre', iconSrc: occupantManIcon },
  { value: 'single-woman', label: 'Solo mujer', iconSrc: occupantWomanIcon },
  { value: 'family', label: 'Con niños', iconSrc: occupantFamilyIcon },
  { value: 'any', label: 'Sin restricción', iconSrc: occupantAnyIcon },
]

export function HomeMandatorySearch() {
  const { filters, setFilters, query, setQuery, rentalMode, addSearchHistory } = useApp()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<ListingAccessProfile>(readListingAccessProfile)
  const [error, setError] = useState('')
  const canSearch = useMemo(() => hasListingAccessSelection(profile), [profile])

  const selectOccupant = (value: Exclude<HomeOccupantChoice, null>) => {
    setProfile((current) => ({ ...current, occupant: current.occupant === value ? null : value }))
    setError('')
  }

  const selectBoolean = (key: 'pets' | 'smoking', value: 'Sí' | 'No') => {
    setProfile((current) => ({ ...current, [key]: current[key] === value ? 'Cualquiera' : value }))
    setError('')
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!canSearch) {
      setError('Selecciona al menos una condición para ver los anuncios.')
      return
    }

    const location = resolveTenerifeLocation(query.trim() || 'Tenerife')
    if (!location) {
      setError('En esta versión solo puedes buscar habitaciones en Tenerife.')
      return
    }

    const normalized = location.normalizedValue
    const exactArea = location.type === 'area' || location.type === 'district' ? normalized : undefined
    const nextFilters = applyListingAccessProfile({
      ...filters,
      areas: exactArea ? [exactArea] : location.type === 'island' ? filters.areas : [],
    }, profile)

    persistListingAccessProfile(profile)
    setFilters(nextFilters)
    setQuery(normalized)
    addSearchHistory(normalized)

    const params = filtersToParams(
      nextFilters,
      new URLSearchParams({ q: normalized, alquiler: rentalMode }),
    )
    navigate(`/buscar?${params.toString()}`)
  }

  return <form className="mandatory-home-search" onSubmit={submit}>
    <div className="mandatory-home-search__rental">
      <span>Tipo de alquiler <small>opcional</small></span>
      <RentalTypeSwitch home />
    </div>

    <fieldset className="mandatory-choice-group">
      <legend>¿Para quién buscas?</legend>
      <p>Selecciona una opción de ocupación.</p>
      <div className="mandatory-choice-grid mandatory-choice-grid--occupants">
        {occupantOptions.map(({ value, label, iconSrc }) => <button
          key={value}
          type="button"
          className={cn('mandatory-choice', profile.occupant === value && 'is-selected')}
          aria-pressed={profile.occupant === value}
          onClick={() => selectOccupant(value)}
        >
          <img className="mandatory-choice__reference-icon" src={iconSrc} alt="" aria-hidden="true" />
          <span>{label}</span>
        </button>)}
      </div>
    </fieldset>

    <fieldset className="mandatory-choice-group">
      <legend>Mascotas</legend>
      <p>Indica si necesitas una habitación que las admita.</p>
      <div className="mandatory-choice-grid">
        <button type="button" className={cn('mandatory-choice', profile.pets === 'Sí' && 'is-selected')} aria-pressed={profile.pets === 'Sí'} onClick={() => selectBoolean('pets', 'Sí')}><img className="mandatory-choice__reference-icon" src={occupantPetsIcon} alt="" aria-hidden="true" /><span>Con mascotas</span></button>
        <button type="button" className={cn('mandatory-choice', profile.pets === 'No' && 'is-selected')} aria-pressed={profile.pets === 'No'} onClick={() => selectBoolean('pets', 'No')}><PawPrint aria-hidden="true" /><span>Sin mascotas</span></button>
      </div>
    </fieldset>

    <fieldset className="mandatory-choice-group">
      <legend>Tabaco</legend>
      <p>Selecciona la condición que necesitas.</p>
      <div className="mandatory-choice-grid">
        <button type="button" className={cn('mandatory-choice', profile.smoking === 'Sí' && 'is-selected')} aria-pressed={profile.smoking === 'Sí'} onClick={() => selectBoolean('smoking', 'Sí')}><Cigarette aria-hidden="true" /><span>Para fumadores</span></button>
        <button type="button" className={cn('mandatory-choice', profile.smoking === 'No' && 'is-selected')} aria-pressed={profile.smoking === 'No'} onClick={() => selectBoolean('smoking', 'No')}><CigaretteOff aria-hidden="true" /><span>No fumadores</span></button>
      </div>
    </fieldset>

    <div className="mandatory-home-search__location">
      <SearchLocationInput home value={query} onChange={(value) => { setQuery(value); setError('') }} />
    </div>

    {error ? <p className="mandatory-home-search__error" role="alert">{error}</p> : null}

    <Button type="submit" size="lg" disabled={!canSearch} aria-disabled={!canSearch}>
      <Search data-icon="inline-start" />
      Ver habitaciones
    </Button>
    {!canSearch ? <small className="mandatory-home-search__locked">Elige al menos una condición para desbloquear los anuncios.</small> : null}
  </form>
}
