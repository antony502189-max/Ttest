import { writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const OUTPUT = path.join(ROOT, 'src', 'data', 'maps', 'tenerife-zone-hierarchy.geojson')

const SOURCES = {
  istacDistricts: 'https://datos.canarias.es/catalogos/estadisticas/dataset/e482c213-9f04-483b-b17c-00bc34a4c359/resource/29612105-362d-4f98-af02-71858da33ad9/download/distritos_20240101_generalizada.json',
  santaCruzDistricts: 'https://www.santacruzdetenerife.es/opendata/dataset/f1728492-96a2-4b5f-8d89-ad932ff1f489/resource/0cae87a8-b1ba-4f9c-a963-2abcc1b926a2/download/distritos.geojson',
  santaCruzNeighbourhoods: 'https://www.santacruzdetenerife.es/opendata/dataset/1c6ff264-2013-4308-8479-721116041a64/resource/10d89a65-bb55-4947-b04e-c2f9000e7297/download/barrios_2016.geojson',
}

const slugify = (value) => value
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('es-ES')
  .replace(/[^a-z0-9]+/g, '-')
  .replace(/(^-|-$)/g, '')

async function getJson(url) {
  const response = await fetch(url, { headers: { accept: 'application/geo+json, application/json' } })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${url}`)
  return response.json()
}

function districtId(label) {
  return `district:santa-cruz-de-tenerife:${slugify(label)}`
}

const [istac, santaCruzDistricts, santaCruzNeighbourhoods] = await Promise.all([
  getJson(SOURCES.istacDistricts),
  getJson(SOURCES.santaCruzDistricts),
  getJson(SOURCES.santaCruzNeighbourhoods),
])

const laLaguna = istac.features
  .filter((feature) => feature.properties?.gcd_municipio === '38023')
  .map((feature) => {
    const number = String(feature.properties.geocode).match(/_D(\d+)$/)?.[1]
    if (!number) throw new Error(`Unexpected ISTAC district id: ${feature.properties.geocode}`)
    return {
      type: 'Feature',
      id: `district:san-cristobal-de-la-laguna:${number}`,
      properties: {
        id: `district:san-cristobal-de-la-laguna:${number}`,
        label: `Distrito ${number}`,
        kind: 'district',
        parentId: 'municipality:san-cristobal-de-la-laguna',
        aliases: [`Distrito ${Number(number)} de La Laguna`],
        geometryAvailable: true,
        sourceId: feature.properties.geocode,
        source: 'ISTAC',
      },
      geometry: feature.geometry,
    }
  })

const santaDistricts = santaCruzDistricts.features.map((feature) => {
  const label = String(feature.properties.DISTRITO).trim()
  const id = districtId(label)
  return {
    type: 'Feature',
    id,
    properties: {
      id,
      label: label.replace(/\s+-\s+/g, '-').replace(/\b\w/g, (letter) => letter.toLocaleUpperCase('es-ES')),
      kind: 'district',
      parentId: 'municipality:santa-cruz-de-tenerife',
      aliases: [label],
      geometryAvailable: true,
      sourceId: String(feature.properties.COD_DISTRI),
      source: 'Ayuntamiento de Santa Cruz de Tenerife',
    },
    geometry: feature.geometry,
  }
})

const santaNeighbourhoods = santaCruzNeighbourhoods.features.map((feature) => {
  const label = String(feature.properties.BARRIO).trim()
  const district = String(feature.properties.DISTRITO).trim()
  const code = String(feature.properties.COD_BARRIO).padStart(2, '0')
  const id = `neighbourhood:santa-cruz-de-tenerife:${code}`
  return {
    type: 'Feature',
    id,
    properties: {
      id,
      label: label.replace(/\b\w/g, (letter) => letter.toLocaleUpperCase('es-ES')),
      kind: 'neighbourhood',
      parentId: districtId(district),
      aliases: [label],
      geometryAvailable: true,
      sourceId: code,
      source: 'Ayuntamiento de Santa Cruz de Tenerife',
    },
    geometry: feature.geometry,
  }
})

const collection = {
  type: 'FeatureCollection',
  attribution: 'Distritos de La Laguna: Instituto Canario de Estadística (ISTAC), 2024. Distritos y barrios de Santa Cruz de Tenerife: Ayuntamiento de Santa Cruz de Tenerife, CC BY.',
  retrieved: '2026-07-22',
  sources: [
    {
      id: 'istac-districts-2024',
      url: SOURCES.istacDistricts,
      license: 'ISTAC reuse terms (Ley 37/2007); commercial and non-commercial reuse permitted with attribution and update date',
      legalPrecision: 'Statistical district boundaries for geospatial representation; not cadastral boundaries',
    },
    {
      id: 'santa-cruz-districts',
      url: SOURCES.santaCruzDistricts,
      license: 'CC BY',
      legalPrecision: 'Municipal open-data district boundaries; search aid, not cadastral boundaries',
    },
    {
      id: 'santa-cruz-neighbourhoods-2016',
      url: SOURCES.santaCruzNeighbourhoods,
      license: 'CC BY',
      legalPrecision: '2016 neighbourhood delimitations with demographic attributes removed during transformation',
    },
  ],
  features: [...laLaguna, ...santaDistricts, ...santaNeighbourhoods],
}

await writeFile(OUTPUT, `${JSON.stringify(collection)}\n`, 'utf8')
console.log(JSON.stringify({
  output: path.relative(ROOT, OUTPUT),
  districts: laLaguna.length + santaDistricts.length,
  neighbourhoods: santaNeighbourhoods.length,
  features: collection.features.length,
}))
