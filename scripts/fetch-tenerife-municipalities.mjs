import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const SOURCE = 'https://datos.tenerife.es/ckan/dataset/d0fae4ae-3bd5-41fc-939b-d7b16e3d5bda/resource/98e3a02c-d7bf-4e1e-b54f-a13ca4fee148/download/municip_4326.geojson'
const OUTPUT_DIR = path.resolve('src/data/maps')
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'tenerife-municipalities.geojson')

const canonicalLabels = new Map([
  ['Guia de Isora', 'Guía de Isora'],
  ['Guimar', 'Güímar'],
  ['La Laguna', 'San Cristóbal de La Laguna'],
  ['Santa Ursula', 'Santa Úrsula'],
  ['Vilaflor', 'Vilaflor de Chasna'],
])

const slugify = (value) => value
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('es-ES')
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/(^-|-$)/g, '')

async function fetchJson(attempts = 4) {
  let lastError
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(SOURCE, { headers: { accept: 'application/geo+json, application/json' } })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      return await response.json()
    } catch (error) {
      lastError = error
      if (attempt < attempts) await new Promise((resolve) => setTimeout(resolve, 750 * attempt))
    }
  }
  throw lastError
}

const raw = await fetchJson()
const byMunicipality = new Map()

for (const feature of raw.features ?? []) {
  const sourceLabel = feature.properties?.NOMBRE
  const label = canonicalLabels.get(sourceLabel) ?? sourceLabel
  const nationalCode = feature.properties?.COD_MUNI
  if (!label || !nationalCode || feature.geometry?.type !== 'MultiPolygon') continue
  const current = byMunicipality.get(nationalCode) ?? { label, nationalCode, polygons: [] }
  current.polygons.push(...feature.geometry.coordinates)
  byMunicipality.set(nationalCode, current)
}

const features = [...byMunicipality.values()]
  .sort((left, right) => left.label.localeCompare(right.label, 'es'))
  .map(({ label, nationalCode, polygons }) => ({
    type: 'Feature',
    id: `tenerife-${slugify(label)}`,
    properties: {
      id: slugify(label),
      label,
      kind: 'municipality',
      nationalCode,
    },
    geometry: { type: 'MultiPolygon', coordinates: polygons },
  }))

if (features.length !== 31) throw new Error(`Expected 31 Tenerife municipalities, received ${features.length}`)

const collection = {
  type: 'FeatureCollection',
  name: 'Tenerife municipalities',
  attribution: 'Límites Municipales de Tenerife, Cabildo de Tenerife, CC BY',
  source: SOURCE,
  sourceDate: '2015-11',
  generatedAt: new Date().toISOString(),
  features,
}

await mkdir(OUTPUT_DIR, { recursive: true })
await writeFile(OUTPUT_FILE, `${JSON.stringify(collection)}\n`, 'utf8')
process.stdout.write(`Wrote ${features.length} dissolved municipality features to ${OUTPUT_FILE}\n`)
