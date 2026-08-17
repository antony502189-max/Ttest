from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = Path(path)
    text = target.read_text()
    if text.count(old) < count:
        raise SystemExit(f"{path}: patch anchor not found: {old[:120]!r}")
    target.write_text(text.replace(old, new, count))


i18n = Path("src/contexts/i18n-context.tsx")
text = i18n.read_text()
assign_anchor = "Object.assign(translations, listingTranslations, screenshotLockedTranslations)"
if assign_anchor not in text:
    raise SystemExit("i18n translation merge anchor not found")

room_first = r'''const roomFirstTranslations: Record<string, Translation> = {
  'El precio, las fechas y la duración se adaptan al tipo de alquiler.': { ru: 'Цена, даты и срок зависят от типа аренды.', en: 'Price, dates and duration adapt to the rental type.' },
  'Larga estancia': { ru: 'Долгосрочная аренда', en: 'Long stay' },
  'Precio mensual en euros.': { ru: 'Ежемесячная цена в евро.', en: 'Monthly price in euros.' },
  'Alquiler vacacional': { ru: 'Краткосрочная аренда', en: 'Holiday rental' },
  'Precio por noche en euros.': { ru: 'Цена за ночь в евро.', en: 'Price per night in euros.' },
  'Especializado en habitaciones': { ru: 'Специализировано на комнатах', en: 'Built for room rentals' },
  'Publica una habitación completa o, si es compartida, plazas/camas individuales. Las condiciones se muestran antes del contacto.': { ru: 'Разместите целую комнату или отдельные места/кровати в общей комнате. Условия видны до связи с владельцем.', en: 'List a whole room or individual bed spaces in a shared room. Conditions are shown before contact.' },
  'La dirección exacta no se muestra públicamente.': { ru: 'Точный адрес публично не показывается.', en: 'The exact address is not shown publicly.' },
  'Mostraremos un punto aproximado.': { ru: 'Мы покажем примерную точку.', en: 'We will show an approximate point.' },
  'Selecciona un punto aproximado': { ru: 'Выберите примерную точку', en: 'Select an approximate point' },
  'El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.': { ru: 'Маркер расположен в выбранном районе. Его можно немного сдвинуть, не раскрывая точную улицу.', en: 'The marker is centred in the area. Move it slightly without publishing the exact street.' },
  'Centrar de nuevo en la zona': { ru: 'Снова центрировать в районе', en: 'Re-centre in the area' },
  'Describe la habitación': { ru: 'Опишите комнату', en: 'Describe the room' },
  'Datos estructurados de la habitación, las plazas y la vivienda.': { ru: 'Структурированные данные о комнате, местах и жилье.', en: 'Structured details about the room, spaces and home.' },
  'Habitación privada': { ru: 'Отдельная комната', en: 'Private room' },
  'Se alquila una habitación separada.': { ru: 'Сдаётся отдельная комната.', en: 'A separate room is rented out.' },
  'Puede alojar a varias personas y admitir plazas individuales.': { ru: 'Подходит для нескольких человек и может сдаваться по отдельным местам.', en: 'Can accommodate several people and allow individual bed spaces.' },
  'Espacio autónomo que se alquila completo.': { ru: 'Автономное пространство, которое сдаётся целиком.', en: 'A self-contained space rented as a whole.' },
  'Habitación completa': { ru: 'Комната целиком', en: 'Whole room' },
  'Un grupo alquila toda la habitación.': { ru: 'Группа арендует всю комнату.', en: 'A group rents the whole room.' },
  'Plazas / camas': { ru: 'Места / кровати', en: 'Bed spaces' },
  'Se alquilan plazas individuales dentro de la habitación.': { ru: 'В комнате сдаются отдельные места.', en: 'Individual bed spaces are rented within the room.' },
  'Superficie de la habitación (m²)': { ru: 'Площадь комнаты (м²)', en: 'Room size (m²)' },
  'Superficie total de la vivienda (m²)': { ru: 'Общая площадь жилья (м²)', en: 'Total home size (m²)' },
  'Número de habitaciones de la vivienda': { ru: 'Количество комнат в жилье', en: 'Number of rooms in the home' },
  'Número de baños / cuartos de baño': { ru: 'Количество ванных комнат', en: 'Number of bathrooms' },
  'Personas que ya viven en la vivienda': { ru: 'Уже проживает в жилье', en: 'People already living in the home' },
  'Capacidad total de esta habitación': { ru: 'Общая вместимость комнаты', en: 'Total room capacity' },
  'Personas que ya viven en esta habitación': { ru: 'Уже проживает в этой комнате', en: 'People already living in this room' },
  'Tipo de cama': { ru: 'Тип кровати', en: 'Bed type' },
  'Número de camas': { ru: 'Количество кроватей', en: 'Number of beds' },
  'Aseo / WC': { ru: 'Туалет / WC', en: 'Toilet / WC' },
  'Aseo compartido': { ru: 'Общий туалет', en: 'Shared toilet' },
  'Aseo privado': { ru: 'Собственный туалет', en: 'Private toilet' },
  'Ducha': { ru: 'Душ', en: 'Shower' },
  'Ducha compartida': { ru: 'Общий душ', en: 'Shared shower' },
  'Ducha privada': { ru: 'Собственный душ', en: 'Private shower' },
  'Calefacción': { ru: 'Отопление', en: 'Heating' },
  'Sin calefacción': { ru: 'Без отопления', en: 'No heating' },
  'Calefacción individual': { ru: 'Индивидуальное отопление', en: 'Individual heating' },
  'Calefacción central': { ru: 'Центральное отопление', en: 'Central heating' },
  'Calefacción no especificada': { ru: 'Отопление не указано', en: 'Heating not specified' },
  'No especificado': { ru: 'Не указано', en: 'Not specified' },
  'Equipamiento y accesibilidad': { ru: 'Оснащение и доступность', en: 'Equipment and accessibility' },
  'Adaptada para personas con movilidad reducida': { ru: 'Адаптировано для людей с ограниченной мобильностью', en: 'Adapted for people with reduced mobility' },
  'Adaptada para movilidad reducida': { ru: 'Адаптировано для маломобильных людей', en: 'Adapted for reduced mobility' },
  'No indicada como adaptada': { ru: 'Не указано как адаптированное', en: 'Not marked as accessible' },
  'Todos los importes se introducen y se muestran en euros (€).': { ru: 'Все суммы вводятся и отображаются в евро (€).', en: 'All amounts are entered and shown in euros (€).' },
  'Precio por noche (€)': { ru: 'Цена за ночь (€)', en: 'Price per night (€)' },
  'Precio por semana (€)': { ru: 'Цена за неделю (€)', en: 'Price per week (€)' },
  'Precio por mes (€)': { ru: 'Цена за месяц (€)', en: 'Price per month (€)' },
  'Fianza / depósito (€)': { ru: 'Залог / депозит (€)', en: 'Deposit (€)' },
  'Indica desde qué día está disponible. La fecha final es opcional; si no la conoces, basta con indicar la estancia mínima.': { ru: 'Укажите дату, с которой жильё доступно. Конечная дата необязательна; если она неизвестна, достаточно указать минимальный срок.', en: 'State the date from which it is available. The end date is optional; if unknown, the minimum stay is enough.' },
  'Estancia mínima (meses)': { ru: 'Минимальный срок (месяцы)', en: 'Minimum stay (months)' },
  'Estancia mínima (noches)': { ru: 'Минимальный срок (ночи)', en: 'Minimum stay (nights)' },
  'Condiciones de convivencia': { ru: 'Условия совместного проживания', en: 'Household conditions' },
  'Distingue quién vive en la vivienda y qué perfiles acepta el anunciante.': { ru: 'Укажите, кто уже живёт в жилье и каких жильцов принимает владелец.', en: 'Specify who already lives in the home and which tenant profiles the advertiser accepts.' },
  'Requisito para la persona inquilina': { ru: 'Требование к жильцу', en: 'Tenant requirement' },
  'Quién vive actualmente en la vivienda': { ru: 'Кто сейчас живёт в жилье', en: 'Who currently lives in the home' },
  'Hombres': { ru: 'Мужчины', en: 'Men' },
  'Mujeres': { ru: 'Женщины', en: 'Women' },
  'Convivencia mixta': { ru: 'Смешанный состав жильцов', en: 'Mixed household' },
  'Perfiles admitidos': { ru: 'Допустимые жильцы', en: 'Accepted tenant profiles' },
  'Parejas': { ru: 'Пары', en: 'Couples' },
  'Familias': { ru: 'Семьи', en: 'Families' },
  'Convivencia y normas': { ru: 'Совместное проживание и правила', en: 'Household and rules' },
  'Actualmente viven niños en la vivienda': { ru: 'Сейчас в жилье живут дети', en: 'Children currently live in the home' },
  'Se aceptan parejas': { ru: 'Можно парам', en: 'Couples accepted' },
  'Se aceptan menores / niños': { ru: 'Можно с детьми', en: 'Children accepted' },
  'La primera será la portada. Puedes reordenarlas.': { ru: 'Первая фотография будет обложкой. Порядок можно изменить.', en: 'The first photo will be the cover. You can reorder them.' },
  'Responde las dudas habituales.': { ru: 'Ответьте на основные вопросы.', en: 'Answer the usual questions.' },
  'Habitación y plazas': { ru: 'Комната и места', en: 'Room and spaces' },
  'Vivienda y espacios': { ru: 'Жильё и помещения', en: 'Home and spaces' },
  'Composición actual': { ru: 'Текущий состав жильцов', en: 'Current household' },
  'Niños viviendo actualmente': { ru: 'Сейчас живут дети', en: 'Children currently living here' },
  'Permitidas': { ru: 'Разрешены', en: 'Allowed' },
  'No permitidas': { ru: 'Не разрешены', en: 'Not allowed' },
  'Todas las condiciones están visibles antes del contacto.': { ru: 'Все условия видны до связи с владельцем.', en: 'All conditions are visible before contact.' },
  'Semana': { ru: 'Неделя', en: 'Week' },
  'Mes': { ru: 'Месяц', en: 'Month' },
  'Condición principal': { ru: 'Главное условие', en: 'Main condition' },
  'Comprueba esta preferencia visible del anunciante antes de contactar. Puedes seguir consultando el anuncio sin interrupciones.': { ru: 'Проверьте это условие владельца перед связью. Просматривать объявление можно без ограничений.', en: 'Check this visible advertiser preference before making contact. You can continue viewing the listing without interruption.' },
  'Se alquilan plazas individuales': { ru: 'Сдаются отдельные места', en: 'Individual bed spaces for rent' },
  'Se alquila la habitación completa': { ru: 'Комната сдаётся целиком', en: 'Whole room for rent' },
  'Resumen de la habitación': { ru: 'Краткая информация о комнате', en: 'Room summary' },
  'Fibra': { ru: 'Wi-Fi', en: 'Wi-Fi' },
  'Fibra 600 Mb': { ru: 'Wi-Fi', en: 'Wi-Fi' },
  'Fibra 1 Gb': { ru: 'Wi-Fi', en: 'Wi-Fi' },
  '/mes': { ru: '/мес.', en: '/month' },
  '/noche': { ru: '/ночь', en: '/night' },
}

'''
text = text.replace(assign_anchor, room_first + "Object.assign(translations, listingTranslations, screenshotLockedTranslations, roomFirstTranslations)", 1)

pattern_anchor = "  let match: RegExpMatchArray | null\n"
if pattern_anchor not in text:
    raise SystemExit("translatePattern anchor not found")
patterns = r'''  if ((match = source.match(/^Gastos aparte: aprox\. (.+) €\/mes$/))) return target(`Коммунальные расходы отдельно: примерно ${match[1]} €/мес.`, `Utilities extra: approx. €${match[1]}/month`)
  if ((match = source.match(/^(\d+) (?:plaza libre|plazas libres)$/))) return target(`Свободных мест: ${match[1]}`, `${match[1]} ${match[1] === '1' ? 'space' : 'spaces'} available`)
  if ((match = source.match(/^Capacidad: (\d+) (?:persona|personas)$/))) return target(`Вместимость: ${match[1]} чел.`, `Capacity: ${match[1]} ${match[1] === '1' ? 'person' : 'people'}`)
  if ((match = source.match(/^Ya viven en esta habitación: (.+)$/))) return target(`Уже живут в этой комнате: ${match[1]}`, `Already living in this room: ${match[1]}`)
  if ((match = source.match(/^Plazas libres: (.+)$/))) return target(`Свободных мест: ${match[1]}`, `Available spaces: ${match[1]}`)
  if ((match = source.match(/^Superficie de la habitación: (.+)$/))) return target(`Площадь комнаты: ${match[1]}`, `Room size: ${match[1]}`)
  if ((match = source.match(/^Superficie total: (.+)$/))) return target(`Общая площадь: ${match[1]}`, `Total size: ${match[1]}`)
  if ((match = source.match(/^(\d+) habitaciones en la vivienda$/))) return target(`Комнат в жилье: ${match[1]}`, `${match[1]} ${match[1] === '1' ? 'room' : 'rooms'} in the home`)
  if ((match = source.match(/^(\d+) (?:baño|baños) en la vivienda$/))) return target(`Ванных комнат: ${match[1]}`, `${match[1]} ${match[1] === '1' ? 'bathroom' : 'bathrooms'} in the home`)
  if ((match = source.match(/^(\d+) residentes actuales en la vivienda$/))) return target(`Сейчас проживает: ${match[1]}`, `${match[1]} current ${match[1] === '1' ? 'resident' : 'residents'} in the home`)
  if ((match = source.match(/^(\d+(?:[.,]\d+)?) €\/(mes|noche)$/))) return target(`${match[1]} €/${match[2] === 'mes' ? 'мес.' : 'ночь'}`, `${match[1]} €/${match[2] === 'mes' ? 'month' : 'night'}`)
'''
text = text.replace(pattern_anchor, pattern_anchor + patterns, 1)
i18n.write_text(text)

old_labels = """function updatePublishRequirementLabels() {
  const labels: Record<string, string> = {
    'single-man': 'Solo hombre',
    'single-woman': 'Solo mujer',
    'single-person': '1 persona',
    couple: '2 personas (pareja/amigos)',
    any: 'Sin restricciones',
  }
  document.querySelectorAll<HTMLOptionElement>('#publish-tenant-requirement option').forEach((option) => {
    const label = labels[option.value]
    if (label && option.textContent !== label) option.textContent = label
  })
}"""
new_labels = """function updatePublishRequirementLabels() {
  const locale = detectOccupantLocale()
  const labels: Record<OccupantLocale, Record<string, string>> = {
    es: { 'single-man': 'Solo hombre', 'single-woman': 'Solo mujer', 'single-person': '1 persona', couple: '2 personas (pareja/amigos)', any: 'Sin restricciones' },
    en: { 'single-man': 'Man only', 'single-woman': 'Woman only', 'single-person': '1 person', couple: '2 people (couple/friends)', any: 'No restrictions' },
    ru: { 'single-man': 'Только мужчина', 'single-woman': 'Только женщина', 'single-person': '1 человек', couple: '2 человека (пара/друзья)', any: 'Без ограничений' },
  }
  document.querySelectorAll<HTMLOptionElement>('#publish-tenant-requirement option').forEach((option) => {
    const label = labels[locale][option.value]
    if (label && option.textContent !== label) option.textContent = label
  })
}"""
replace("src/components/customer-feedback-fixes.tsx", old_labels, new_labels)

replace(
    "src/pages/PublishPage.tsx",
    '<option value="none">Sin calefacción</option><option value="individual">Individual</option><option value="central">Central</option><option value="unknown">No especificado</option>',
    '<option value="none">Sin calefacción</option><option value="individual">Calefacción individual</option><option value="central">Calefacción central</option><option value="unknown">No especificado</option>',
)

Path("src/lib/i18n-locale.ts").write_text(
    '''export type SupportedLocale = "es-ES" | "ru-RU" | "en-GB";\n\nexport function currentLocale(): SupportedLocale {\n  let language = typeof document !== "undefined" ? document.documentElement.lang : "";\n  if (typeof localStorage !== "undefined") {\n    try {\n      const stored = localStorage.getItem("112233:language:v1");\n      if (stored === "es" || stored === "ru" || stored === "en") language = stored;\n    } catch {\n      // Document language remains the fallback when storage is unavailable.\n    }\n  }\n  return language === "ru" ? "ru-RU" : language === "en" ? "en-GB" : "es-ES";\n}\n'''
)

locale_patches = [
    ("src/pages/AccountPages.tsx", 'import { toast } from "sonner";\n', 'import { toast } from "sonner";\nimport { currentLocale } from "@/lib/i18n-locale";\n', '.toLocaleString("es-ES")', '.toLocaleString(currentLocale())'),
    ("src/pages/SearchPage.tsx", 'import { useApp } from "@/contexts/app-context";\n', 'import { useApp } from "@/contexts/app-context";\nimport { currentLocale } from "@/lib/i18n-locale";\n', 'new Intl.DateTimeFormat("es-ES", {', 'new Intl.DateTimeFormat(currentLocale(), {'),
    ("src/pages/AdminPage.tsx", "import { useApp } from '@/contexts/app-context'\n", "import { useApp } from '@/contexts/app-context'\nimport { currentLocale } from '@/lib/i18n-locale'\n", "new Intl.DateTimeFormat('es-ES', {", "new Intl.DateTimeFormat(currentLocale(), {"),
    ("src/pages/MobilePages.tsx", "import { useApp } from '@/contexts/app-context'\n", "import { useApp } from '@/contexts/app-context'\nimport { currentLocale } from '@/lib/i18n-locale'\n", "new Intl.DateTimeFormat('es-ES', {", "new Intl.DateTimeFormat(currentLocale(), {"),
    ("src/pages/ListingPage.tsx", "import { useApp } from '@/contexts/app-context'\n", "import { useApp } from '@/contexts/app-context'\nimport { currentLocale } from '@/lib/i18n-locale'\n", "new Intl.DateTimeFormat('es-ES', {", "new Intl.DateTimeFormat(currentLocale(), {"),
    ("src/components/marketplace.tsx", 'import { toast } from "sonner";\n', 'import { toast } from "sonner";\nimport { currentLocale } from "@/lib/i18n-locale";\n', 'new Intl.NumberFormat("es-ES", {', 'new Intl.NumberFormat(currentLocale(), {'),
    ("src/components/moderation-gate.tsx", "import { useApp } from '@/contexts/app-context'\n", "import { useApp } from '@/contexts/app-context'\nimport { currentLocale } from '@/lib/i18n-locale'\n", "new Intl.DateTimeFormat('es-ES', {", "new Intl.DateTimeFormat(currentLocale(), {"),
]
for path, import_old, import_new, value_old, value_new in locale_patches:
    replace(path, import_old, import_new)
    replace(path, value_old, value_new)

Path("tests/i18n-language-regression.spec.ts").write_text(r'''import { expect, test, type Page } from '@playwright/test'
import { translateText } from '../src/contexts/i18n-context'

async function openAsHost(page: Page, language: 'ru' | 'en', route = '/#/publicar') {
  await page.goto('/#/')
  await page.evaluate(({ language }) => {
    localStorage.clear()
    localStorage.setItem('112233:language:v1', language)
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, { language })
  await page.goto(route)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
}

test('room-first translation dictionary covers dynamic facts', () => {
  expect(translateText('Calefacción', 'ru')).toBe('Отопление')
  expect(translateText('Calefacción', 'en')).toBe('Heating')
  expect(translateText('Equipamiento y accesibilidad', 'ru')).toBe('Оснащение и доступность')
  expect(translateText('Equipamiento y accesibilidad', 'en')).toBe('Equipment and accessibility')
  expect(translateText('Gastos aparte: aprox. 45 €/mes', 'ru')).toBe('Коммунальные расходы отдельно: примерно 45 €/мес.')
  expect(translateText('Gastos aparte: aprox. 45 €/mes', 'en')).toBe('Utilities extra: approx. €45/month')
  expect(translateText('Se alquila la habitación completa', 'ru')).toBe('Комната сдаётся целиком')
  expect(translateText('Se alquila la habitación completa', 'en')).toBe('Whole room for rent')
  expect(translateText('Fibra', 'ru')).toBe('Wi-Fi')
  expect(translateText('Fibra', 'en')).toBe('Wi-Fi')
})

for (const language of ['ru', 'en'] as const) {
  test(`publish room details stay localized in ${language}`, async ({ page }) => {
    await openAsHost(page, language)
    const continueLabel = language === 'ru' ? 'Продолжить' : 'Continue'
    await page.getByRole('button', { name: continueLabel }).click()
    await page.getByRole('button', { name: continueLabel }).click()
    const expected = language === 'ru'
      ? ['Отопление', 'Оснащение и доступность', 'Тип кровати', 'Количество кроватей', 'Туалет / WC', 'Душ']
      : ['Heating', 'Equipment and accessibility', 'Bed type', 'Number of beds', 'Toilet / WC', 'Shower']
    for (const label of expected) await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
    for (const spanish of ['Calefacción', 'Equipamiento y accesibilidad', 'Tipo de cama', 'Número de camas', 'Aseo / WC', 'Ducha']) {
      await expect(page.getByText(spanish, { exact: true })).toHaveCount(0)
    }
  })
}

test('English search does not leak known Spanish room-first labels', async ({ page }) => {
  await openAsHost(page, 'en', '/#/buscar?q=Tenerife&alquiler=long')
  await page.waitForTimeout(300)
  const body = await page.locator('body').innerText()
  for (const spanish of ['Calefacción', 'Sin calefacción', 'Tipo de cama', 'Aseo / WC', 'Ducha', 'Habitación privada', 'Habitación completa', 'Adaptada para movilidad reducida', 'Gastos aparte: aprox.']) {
    expect(body).not.toContain(spanish)
  }
})

test('publish requirement post-processing follows English instead of restoring Spanish', async ({ page }) => {
  await openAsHost(page, 'en')
  for (let step = 0; step < 5; step += 1) await page.getByRole('button', { name: 'Continue' }).click()
  const options = await page.locator('#publish-tenant-requirement option').allTextContents()
  expect(options).toEqual(['Man only', 'Woman only', '1 person', '2 people (couple/friends)', 'No restrictions'])
})
''')

print("i18n patch applied")
