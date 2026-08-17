from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = Path(path)
    text = target.read_text()
    if text.count(old) < count:
        raise SystemExit(f"{path}: patch anchor not found: {old[:120]!r}")
    target.write_text(text.replace(old, new, count))


i18n = Path("src/contexts/i18n-context.tsx")
text = i18n.read_text()
merge_anchor = "}\n\nObject.assign(translations, listingTranslations, screenshotLockedTranslations, roomFirstTranslations)"
if merge_anchor not in text:
    raise SystemExit("roomFirstTranslations closing anchor not found")

extra_exact = r'''  'Anfitrión': { ru: 'Хозяин', en: 'Host' },
  'Aparcamiento': { ru: 'Парковка', en: 'Parking' },
  'Más antiguos': { ru: 'Сначала старые', en: 'Oldest' },
  'Precio más alto': { ru: 'Сначала дороже', en: 'Highest price' },
  'Sin niños': { ru: 'Без детей', en: 'No children' },
  'Particular': { ru: 'Частное лицо', en: 'Private advertiser' },
  'Crea tu perfil': { ru: 'Создайте профиль', en: 'Create your profile' },
  'Sin restricciones': { ru: 'Без ограничений', en: 'No restrictions' },
  '1 persona': { ru: '1 человек', en: '1 person' },
  '2 personas (pareja/amigos)': { ru: '2 человека (пара/друзья)', en: '2 people (couple/friends)' },
  'Habitación doble cerca de la playa y la guagua': { ru: 'Двухместная комната рядом с пляжем и автобусом', en: 'Double room near the beach and bus stops' },
  'Habitación tranquila en piso compartido reformado': { ru: 'Тихая комната в отремонтированной общей квартире', en: 'Quiet room in a renovated shared flat' },
  'Habitación amueblada junto a todos los servicios': { ru: 'Меблированная комната рядом со всей инфраструктурой', en: 'Furnished room close to all amenities' },
  'Habitación exterior con armario empotrado': { ru: 'Светлая комната со встроенным шкафом', en: 'Bright room with built-in wardrobe' },
  'Habitación amplia con balcón y Wi-Fi': { ru: 'Просторная комната с балконом и Wi-Fi', en: 'Spacious room with balcony and Wi-Fi' },
  'Habitación económica en vivienda organizada': { ru: 'Недорогая комната в аккуратном общем жилье', en: 'Affordable room in a well-organised shared home' },
  'Habitación exterior y cuidada en una vivienda compartida con buena conexión. El anuncio detalla gastos, disponibilidad y normas para que puedas comparar antes de contactar.': { ru: 'Светлая ухоженная комната в общем жилье с хорошей транспортной доступностью. В объявлении указаны расходы, доступность и правила, чтобы можно было сравнить варианты до связи.', en: 'Bright, well-kept room in a shared home with good transport links. The listing details costs, availability and rules so you can compare before contacting.' },
'''
text = text.replace(merge_anchor, extra_exact + merge_anchor, 1)

pattern_anchor = "  let match: RegExpMatchArray | null\n"
if pattern_anchor not in text:
    raise SystemExit("translatePattern match anchor not found")

extra_patterns = r'''  const localizeSpanishDate = (value: string) => {
    const ruMonths: Record<string, string> = {
      enero: 'января', febrero: 'февраля', marzo: 'марта', abril: 'апреля', mayo: 'мая', junio: 'июня',
      julio: 'июля', agosto: 'августа', septiembre: 'сентября', octubre: 'октября', noviembre: 'ноября', diciembre: 'декабря',
    }
    const enMonths: Record<string, string> = {
      enero: 'January', febrero: 'February', marzo: 'March', abril: 'April', mayo: 'May', junio: 'June',
      julio: 'July', agosto: 'August', septiembre: 'September', octubre: 'October', noviembre: 'November', diciembre: 'December',
    }
    const months = language === 'ru' ? ruMonths : enMonths
    return value.replace(/\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b/gi, (month) => months[month.toLowerCase()] ?? month)
  }
  if ((match = source.match(/^Gastos aparte: aprox\. (.+) €$/))) return target(`Коммунальные расходы отдельно: примерно ${match[1]} €`, `Utilities extra: approx. €${match[1]}`)
  if ((match = source.match(/^Disponible desde (.+)$/))) return target(`Доступно с ${localizeSpanishDate(match[1])}`, `Available from ${localizeSpanishDate(match[1])}`)
  if ((match = source.match(/^(\d+) residentes · (.+)$/))) return target(`${match[1]} жильцов · ${match[2]}`, `${match[1]} ${match[1] === '1' ? 'resident' : 'residents'} · ${match[2]}`)
  if ((match = source.match(/^Habitación para (\d+) (?:persona|personas)$/))) return target(`Комната для ${match[1]} чел.`, `Room for ${match[1]} ${match[1] === '1' ? 'person' : 'people'}`)
  if ((match = source.match(/^\+(\d+) condiciones$/))) return target(`+${match[1]} условий`, `+${match[1]} conditions`)
  if ((match = source.match(/^Publicado hace (\d+) días$/))) return target(`Опубликовано ${match[1]} дн. назад`, `Published ${match[1]} days ago`)
  if ((match = source.match(/^(\d+) habitaciones en (.+)$/))) return target(`${match[1]} комнат в ${match[2]}`, `${match[1]} rooms in ${match[2]}`)
  if ((match = source.match(/^(\d+) rooms en (.+)$/))) return target(`${match[1]} комнат в ${match[2]}`, `${match[1]} rooms in ${match[2]}`)
'''
text = text.replace(pattern_anchor, pattern_anchor + extra_patterns, 1)
i18n.write_text(text)

# Strengthen the permanent English-search regression with the residues found by the runtime audit.
test_path = Path("tests/i18n-language-regression.spec.ts")
test_text = test_path.read_text()
old = "for (const spanish of ['Calefacción', 'Sin calefacción', 'Tipo de cama', 'Aseo / WC', 'Ducha', 'Habitación privada', 'Habitación completa', 'Adaptada para movilidad reducida', 'Gastos aparte: aprox.']) {"
new = "for (const spanish of ['Calefacción', 'Sin calefacción', 'Tipo de cama', 'Aseo / WC', 'Ducha', 'Habitación privada', 'Habitación completa', 'Adaptada para movilidad reducida', 'Gastos aparte: aprox.', 'Disponible desde', 'Publicado hace', ' residentes · ', 'Habitación para', ' condiciones', 'Particular', 'Anfitrión', 'Aparcamiento', 'Más antiguos', 'Precio más alto', 'Sin niños', 'Crea tu perfil', ' personas (pareja/amigos)', ' habitaciones en ']) {"
if old not in test_text:
    raise SystemExit("English leakage test anchor not found")
test_path.write_text(test_text.replace(old, new, 1))

print("search/card i18n follow-up applied")
