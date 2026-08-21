import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const root = join(import.meta.dirname, '..', 'src')
const componentRoots = [join(root, 'components'), join(root, 'pages')]
const forbiddenPresentationLabels = /(?:Cama individual|Cama doble|Litera|Односпальная кровать|Двуспальная кровать|Двухъярусная кровать|Single bed|Double bed|Bunk bed)/u

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return files(path)
    return /\.tsx?$/.test(entry.name) ? [path] : []
  })
}

const violations = componentRoots.flatMap(files).flatMap((file) => {
  const source = readFileSync(file, 'utf8')
  return source.split(/\r?\n/).flatMap((line, index) => forbiddenPresentationLabels.test(line) ? [`${file}:${index + 1}`] : [])
})

if (violations.length) {
  throw new Error(`Bed-type presentation labels must use src/lib/bed-type-label.ts:\n${violations.join('\n')}`)
}

console.log('i18n-source-guard: ok')
