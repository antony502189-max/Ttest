import { useEffect, useMemo, useState } from 'react'
import { Check, Trash2, X } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { EmptyState, PropertyCard } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import '@/favorites-selection.css'

type FavoritesCopy = {
  eyebrow: string
  title: string
  savedCount: (count: number) => string
  keepSearching: string
  startDelete: string
  cancel: string
  selectAll: string
  clearSelection: string
  selectedCount: (count: number) => string
  deleteSelected: (count: number) => string
  selectListing: (title: string) => string
  deselectListing: (title: string) => string
  deleted: (count: number) => string
}

const copyByLanguage: Record<Language, FavoritesCopy> = {
  es: {
    eyebrow: 'Tu selección',
    title: 'Favoritos',
    savedCount: (count) => `${count} ${count === 1 ? 'habitación guardada' : 'habitaciones guardadas'}`,
    keepSearching: 'Seguir buscando',
    startDelete: 'Seleccionar favoritos para eliminar',
    cancel: 'Cancelar',
    selectAll: 'Seleccionar todo',
    clearSelection: 'Quitar selección',
    selectedCount: (count) => `${count} ${count === 1 ? 'seleccionado' : 'seleccionados'}`,
    deleteSelected: (count) => `Eliminar seleccionados (${count})`,
    selectListing: (title) => `Seleccionar ${title} para eliminar`,
    deselectListing: (title) => `Quitar ${title} de la selección`,
    deleted: (count) => `${count} ${count === 1 ? 'favorito eliminado' : 'favoritos eliminados'}`,
  },
  ru: {
    eyebrow: 'Ваш выбор',
    title: 'Избранное',
    savedCount: (count) => `${count} ${count === 1 ? 'комната сохранена' : count >= 2 && count <= 4 ? 'комнаты сохранены' : 'комнат сохранено'}`,
    keepSearching: 'Продолжить поиск',
    startDelete: 'Выбрать избранное для удаления',
    cancel: 'Отмена',
    selectAll: 'Выбрать всё',
    clearSelection: 'Снять выделение',
    selectedCount: (count) => `Выбрано: ${count}`,
    deleteSelected: (count) => `Удалить выбранные (${count})`,
    selectListing: (title) => `Выбрать «${title}» для удаления`,
    deselectListing: (title) => `Снять выбор с «${title}»`,
    deleted: (count) => `Удалено из избранного: ${count}`,
  },
  en: {
    eyebrow: 'Your selection',
    title: 'Favorites',
    savedCount: (count) => `${count} saved ${count === 1 ? 'room' : 'rooms'}`,
    keepSearching: 'Keep searching',
    startDelete: 'Select favorites to remove',
    cancel: 'Cancel',
    selectAll: 'Select all',
    clearSelection: 'Clear selection',
    selectedCount: (count) => `${count} selected`,
    deleteSelected: (count) => `Remove selected (${count})`,
    selectListing: (title) => `Select ${title} for removal`,
    deselectListing: (title) => `Deselect ${title}`,
    deleted: (count) => `${count} ${count === 1 ? 'favorite removed' : 'favorites removed'}`,
  },
}

export function FavoritesPage() {
  const { favorites, allListings, toggleFavorite } = useApp()
  const { language } = useI18n()
  const copy = copyByLanguage[language]
  const saved = useMemo(
    () => allListings.filter((listing) => favorites.has(listing.id)),
    [allListings, favorites],
  )
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setSelected((current) => new Set([...current].filter((id) => favorites.has(id))))
  }, [favorites])

  useEffect(() => {
    if (saved.length) return
    setSelecting(false)
    setSelected(new Set())
  }, [saved.length])

  const toggleSelected = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const stopSelecting = () => {
    setSelecting(false)
    setSelected(new Set())
  }

  const allSelected = saved.length > 0 && selected.size === saved.length

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(saved.map((listing) => listing.id)))
  }

  const removeSelected = () => {
    const ids = [...selected].filter((id) => favorites.has(id))
    if (!ids.length) return
    ids.forEach((id) => toggleFavorite(id))
    toast.dismiss()
    toast.success(copy.deleted(ids.length))
    stopSelecting()
  }

  return (
    <div className="container account-page favorites-page">
      <header className="account-heading">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h1>{copy.title}</h1>
          <p>{copy.savedCount(saved.length)}</p>
        </div>
        <div className="favorites-heading-actions">
          <Button asChild variant="outline">
            <Link to="/buscar">{copy.keepSearching}</Link>
          </Button>
          {saved.length ? (
            <Button
              type="button"
              variant={selecting ? 'destructive' : 'outline'}
              size="icon"
              className="favorites-bulk-trigger"
              aria-label={selecting ? copy.cancel : copy.startDelete}
              aria-pressed={selecting}
              onClick={() => {
                if (selecting) stopSelecting()
                else setSelecting(true)
              }}
            >
              {selecting ? <X /> : <Trash2 />}
            </Button>
          ) : null}
        </div>
      </header>

      {selecting && saved.length ? (
        <div className="favorites-selection-bar" role="toolbar" aria-label={copy.startDelete}>
          <strong aria-live="polite">{copy.selectedCount(selected.size)}</strong>
          <div className="favorites-selection-bar__actions">
            <Button type="button" variant="ghost" size="sm" onClick={toggleAll}>
              {allSelected ? copy.clearSelection : copy.selectAll}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={stopSelecting}>
              {copy.cancel}
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={!selected.size}
              onClick={removeSelected}
            >
              <Trash2 data-icon="inline-start" />
              {copy.deleteSelected(selected.size)}
            </Button>
          </div>
        </div>
      ) : null}

      {saved.length ? (
        <div className="property-grid favorites-grid">
          {saved.map((listing) => {
            const isSelected = selected.has(listing.id)
            return (
              <div
                className={`favorite-card${selecting ? ' favorite-card--selecting' : ''}${isSelected ? ' favorite-card--selected' : ''}`}
                key={listing.id}
              >
                <PropertyCard listing={listing} compact />
                {selecting ? (
                  <button
                    type="button"
                    className="favorite-card__selector"
                    aria-pressed={isSelected}
                    aria-label={isSelected ? copy.deselectListing(listing.title) : copy.selectListing(listing.title)}
                    onClick={() => toggleSelected(listing.id)}
                  >
                    <span className="favorite-card__selection-indicator" aria-hidden="true">
                      {isSelected ? <Check /> : null}
                    </span>
                  </button>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : (
        <EmptyState favorites />
      )}
    </div>
  )
}
