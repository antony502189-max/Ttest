import fs from 'node:fs'

function replace(path, before, after, label) {
  const source = fs.readFileSync(path, 'utf8')
  if (!source.includes(before)) throw new Error(`${path}: missing finalizer anchor: ${label}`)
  fs.writeFileSync(path, source.replace(before, after))
}

const layer = 'src/components/mobile-map-listings-layer.tsx'

replace(
  layer,
  '      const markers = items.map((listing) => {',
  '      const markers = items.map((listing, index) => {',
  'marker priority index',
)
replace(
  layer,
  '          collisionBehavior: google.maps.CollisionBehavior.REQUIRED,\n          zIndex: 10,',
  '          collisionBehavior: google.maps.CollisionBehavior.OPTIONAL_AND_HIDES_LOWER_PRIORITY,\n          zIndex: 1000 - index,',
  'non-overlapping marker collision policy',
)
replace(
  layer,
  '      marker.zIndex = active ? 4000 : 10',
  "      marker.zIndex = active ? 4000 : 1000 - Math.max(0, items.findIndex((item) => item.id === id))",
  'preserve marker priority after selection',
)

console.log('Final mobile map interaction fixes applied successfully.')
