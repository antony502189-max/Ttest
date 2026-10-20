import { useEffect, useState, type FormEvent } from 'react'
import { api } from '@/api/client'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type OwnerAddress = { street: string; postcode: string; city: string; municipalityCode: string }

export function OwnerAddressForm() {
  const { language } = useI18n()
  const copy = {
    es: { title: 'Dirección del propietario para TOP', street: 'Calle y número', city: 'Municipio', postal: 'Código postal', save: 'Verificar dirección', checking: 'Verificando…', done: 'Dirección verificada', help: 'Hay tres plazas TOP por municipio del propietario. Verificaremos esta dirección con CartoCiudad (IGN). La dirección es privada.' },
    en: { title: 'Owner address for TOP', street: 'Street and number', city: 'Municipality', postal: 'Postcode', save: 'Verify address', checking: 'Verifying…', done: 'Address verified', help: 'There are three TOP places per owner municipality. We will verify this address with CartoCiudad (IGN). The address is private.' },
    ru: { title: 'Адрес владельца для TOP', street: 'Улица и номер дома', city: 'Муниципалитет', postal: 'Почтовый индекс', save: 'Проверить адрес', checking: 'Проверяем…', done: 'Адрес проверен', help: 'В муниципалитете владельца доступно три места TOP. Адрес проверяется через CartoCiudad (IGN) и не публикуется.' },
  }[language]
  const [draft, setDraft] = useState({ street: '', postcode: '', city: '' })
  const [municipality, setMunicipality] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void api<{ address: OwnerAddress | null }>('/users/me/address', { signal: controller.signal }).then(({ address }) => {
      if (address) { setDraft({ street: address.street, postcode: address.postcode, city: address.city }); setMunicipality(address.city) }
    }).catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message) })
    return () => controller.abort()
  }, [])
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const { address } = await api<{ address: OwnerAddress }>('/users/me/address', { method: 'PUT', body: JSON.stringify(draft) })
      setMunicipality(address.city)
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <form onSubmit={save} className="profile-card" aria-label={copy.title}>
    <h2>{copy.title}</h2><p>{copy.help}</p>
    {(['street', 'postcode', 'city'] as const).map((key) => <label key={key}>{key === 'street' ? copy.street : key === 'city' ? copy.city : copy.postal}
      <Input required maxLength={key === 'postcode' ? 5 : 160} autoComplete={key === 'street' ? 'street-address' : key === 'city' ? 'address-level2' : 'postal-code'}
        value={draft[key]} onChange={(event) => { setDraft({ ...draft, [key]: event.target.value }); setMunicipality('') }} />
    </label>)}
    {municipality ? <p role="status">{copy.done}: {municipality}</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    <Button disabled={busy} type="submit">{busy ? copy.checking : copy.save}</Button>
  </form>
}
