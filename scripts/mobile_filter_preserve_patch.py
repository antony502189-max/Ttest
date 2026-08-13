from pathlib import Path

path = Path('src/components/mobile-search-results-v2.tsx')
text = path.read_text()
old = "    const roomTypes = (params.get('tiposHabitacion') ?? '').split('|').filter((value): value is Listing['roomType'] => ['Habitación individual', 'Habitación compartida', 'Estudio'].includes(value))"
new = "    const explicitRoomTypes = (params.get('tiposHabitacion') ?? '').split('|').filter((value): value is Listing['roomType'] => ['Habitación individual', 'Habitación compartida', 'Estudio'].includes(value))\n    const roomTypes: Listing['roomType'][] = explicitRoomTypes.length ? explicitRoomTypes : parsed.roomType !== 'Cualquiera' ? [parsed.roomType] : []"
if text.count(old) != 1:
    raise SystemExit(f'room type migration match count={text.count(old)}')
text = text.replace(old, new, 1)
needle = "      roomType: 'Cualquiera',\n      roomCapacity: 'Cualquiera',\n"
if text.count(needle) != 3:
    raise SystemExit(f'expected 3 room-capacity reset sites, got {text.count(needle)}')
text = text.replace(needle, "      roomType: 'Cualquiera',\n")
path.write_text(text)
