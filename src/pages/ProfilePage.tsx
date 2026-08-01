import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react'
import { ArrowLeft, LogOut, Trash2, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { ProfilePage as DesktopProfilePage } from '@/pages/AccountPages'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { useMediaUrl } from '@/components/media-image'
import { logoutSession } from '@/api/auth'
import { MediaStorageError, saveMediaFile } from '@/lib/media-storage'
import { ConfirmDialog } from '@/components/forms'
import '@/mobile-app-v2.css'
import '@/auth-account.css'

const copy = {
  es: { title: 'Tu cuenta', photo: 'Añadir foto', data: 'Tus datos', name: 'Nombre', email: 'Email', logout: 'Cerrar sesión', saving: 'Guardando…', saved: 'Guardado', invalidName: 'El nombre debe tener al menos 2 caracteres.', upload: 'No se pudo guardar la foto.', logoutError: 'No se pudo cerrar la sesión. Comprueba la conexión e inténtalo de nuevo.' },
  en: { title: 'Your account', photo: 'Add photo', data: 'Your details', name: 'Name', email: 'Email', logout: 'Sign out', saving: 'Saving…', saved: 'Saved', invalidName: 'The name must contain at least 2 characters.', upload: 'The photo could not be saved.', logoutError: 'The session could not be closed. Check the connection and try again.' },
  ru: { title: 'Ваш аккаунт', photo: 'Добавить фото', data: 'Ваши данные', name: 'Имя', email: 'Email', logout: 'Выйти из аккаунта', saving: 'Сохранение…', saved: 'Сохранено', invalidName: 'Имя должно содержать минимум 2 символа.', upload: 'Не удалось сохранить фотографию.', logoutError: 'Не удалось завершить сессию. Проверьте соединение и повторите попытку.' },
} as const

function useMobileProfileLayout() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px), (max-height: 480px) and (max-width: 900px)').matches)
  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px), (max-height: 480px) and (max-width: 900px)')
    const update = () => setMobile(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return mobile
}

function MobileProfilePage() {
  const navigate = useNavigate()
  const { language } = useI18n()
  const { currentUser, updateProfile, logout, deleteAccount } = useApp()
  const t = copy[language]
  const [name, setName] = useState(currentUser?.name ?? '')
  const [saveState, setSaveState] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const [uploading, setUploading] = useState(false)
  const saveMessageTimer = useRef<number | null>(null)
  const avatarUrl = useMediaUrl(currentUser?.avatarRef)

  useEffect(() => {
    document.documentElement.classList.add('mobile-v2-active')
    return () => {
      document.documentElement.classList.remove('mobile-v2-active')
      if (saveMessageTimer.current) window.clearTimeout(saveMessageTimer.current)
    }
  }, [])

  useEffect(() => { setName(currentUser?.name ?? '') }, [currentUser?.name])
  if (!currentUser) return null

  const saveName = () => {
    const normalized = name.trim()
    if (normalized.length < 2) {
      toast.error(t.invalidName)
      setName(currentUser.name)
      return
    }
    if (normalized === currentUser.name) return
    setSaveState(t.saving)
    updateProfile({ name: normalized })
    setName(normalized)
    setSaveState(t.saved)
    if (saveMessageTimer.current) window.clearTimeout(saveMessageTimer.current)
    saveMessageTimer.current = window.setTimeout(() => setSaveState(''), 1800)
  }

  const handleNameKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return
    event.preventDefault()
    event.currentTarget.blur()
  }

  const uploadPhoto = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      const avatarRef = await saveMediaFile(file)
      updateProfile({ avatarRef })
    } catch (error) {
      toast.error(error instanceof MediaStorageError ? error.message : t.upload)
    } finally {
      setUploading(false)
    }
  }

  const signOut = async () => {
    if (loggingOut) return
    setLoggingOut(true)
    try {
      await logoutSession()
      logout()
      navigate('/acceso', { replace: true })
    } catch {
      toast.error(t.logoutError)
      setLoggingOut(false)
    }
  }

  return <div className="m2-app m2-account-screen notranslate" translate="no">
    <header className="m2-account-appbar">
      <button type="button" onClick={() => navigate(-1)} aria-label={t.title}><ArrowLeft /></button>
      <strong>{t.title}</strong>
      <span aria-hidden="true" />
    </header>
    <main className="m2-account-content">
      <section className="m2-account-avatar-block" aria-label={t.photo}>
        <div className="m2-account-avatar">
          {avatarUrl ? <img src={avatarUrl} alt={currentUser.name} /> : <UserRound aria-hidden="true" />}
        </div>
        <label className="m2-account-photo-action">
          {uploading ? '…' : t.photo}
          <input type="file" accept="image/jpeg,image/png,image/webp" disabled={uploading} onChange={(event) => { void uploadPhoto(event) }} />
        </label>
      </section>

      <h2 className="m2-account-section-title">{t.data}</h2>
      <div className="m2-account-form">
        <div className="m2-account-field">
          <label htmlFor="mobile-profile-name">{t.name}</label>
          <input id="mobile-profile-name" value={name} autoComplete="name" onChange={(event) => setName(event.target.value)} onBlur={saveName} onKeyDown={handleNameKeyDown} />
        </div>
        <div className="m2-account-field">
          <label htmlFor="mobile-profile-email">{t.email}</label>
          <input id="mobile-profile-email" value={currentUser.email} type="email" readOnly aria-readonly="true" />
        </div>
        <p className="m2-account-save-state" role="status" aria-live="polite">{saveState}</p>
        <button type="button" className="m2-account-logout" disabled={loggingOut} onClick={() => { void signOut() }}>
          <LogOut aria-hidden="true" />
          <span>{loggingOut ? '…' : t.logout}</span>
        </button>
        <ConfirmDialog
          trigger={<button type="button" className="m2-account-delete"><Trash2 aria-hidden="true" /><span>Eliminar cuenta</span></button>}
          title="¿Eliminar tu cuenta?"
          description="Se eliminarán esta cuenta local, su sesión, anuncios, borrador, búsquedas, favoritos, historial, comentarios y archivos multimedia sin uso. Esta acción no se puede deshacer."
          confirmLabel="Eliminar definitivamente"
          destructive
          onConfirm={() => { void deleteAccount().then((deleted) => { if (deleted) navigate('/acceso', { replace: true }) }) }}
        />
      </div>
    </main>
  </div>
}

export function ProfilePage() {
  const mobile = useMobileProfileLayout()
  return mobile ? <MobileProfilePage /> : <DesktopProfilePage />
}
