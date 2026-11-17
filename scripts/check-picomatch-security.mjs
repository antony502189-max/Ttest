// Temporary, reviewed fix for GHSA-fc5q-39xc-vjpf until upstream releases a fix.
// This checks actual installed code as well as bounded attack regressions;
// changing the package name alone must never satisfy the security gate.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const require = createRequire(import.meta.url)
const root = path.resolve(import.meta.dirname, '..')
const integrity = 'sha512-JroBFEmaejC7szGSfqOhF1QZHLKvX2wTA1+fWyfkpy3BjzdQKNPLKa2FtgeKVUDy5/UPUNkXEeCHJ5ZRBMLTVA=='
// All shipped bytes match ryotsu-kankichi/secured-picomatch commit
// 3ab5a7627d480259e3d9ca67fbc14c125d374f0e, including the retained MIT license.
const hashes = {
  'index.js': '02ae26406508e28f9ba0865be16cf77f0b33de6c4d4d49c212c4176df1d5625a',
  'LICENSE': 'd0cd141b0c322fded5dfad1d4645bb2fedfc05b7321fe1009469638190d59ef9',
  'package.json': '6a17af861b7ade307d1cc64a389823d3ce0307d78b80eb38f9e110bacac999fc',
  'posix.js': '5695ff5dfcd5a338a40630bd506056f2950bcb08fe1cc068519cbbfe60add480',
  'README.md': 'dbfcccb75df9360390f29d12c6ace93f9db3c6cd6b505158c11bdee572c1c4f2',
  'lib/constants.js': 'cdcb0716c3c7137f34fbec4fe29613de0aaa0a7de01505601ef3a88a5ba05fb0',
  'lib/parse.js': 'a59b25c67cce014f5226836f8391cb1f323dc76224dc82b85c6826d10b33922a',
  'lib/picomatch.js': 'fdd249d7ffff853f3bb1c77eafc8baa1a437bea85a94c35877b83c6a40d9ca94',
  'lib/scan.js': '6457a1764e5c2e543cc3a0c00ce12ebb3764097628868198370b64d4e642aaae',
  'lib/utils.js': 'f04604f70cd1a3f6ace80b84766468674ff38b4bb83818d2ef1d81fc6355f935',
}
const lock = JSON.parse(readFileSync(path.join(root, 'package-lock.json'), 'utf8'))
const copies = Object.entries(lock.packages).filter(([name]) => name.endsWith('/picomatch'))
assert.ok(copies.length > 0, 'Expected a reviewed picomatch dependency')
for (const [location, pkg] of copies) {
  assert.equal(pkg.name, '@ryotsu/picomatch')
  assert.equal(pkg.version, '4.0.7-a')
  assert.equal(pkg.integrity, integrity)
  assert.equal(pkg.resolved, 'https://registry.npmjs.org/@ryotsu/picomatch/-/picomatch-4.0.7-a.tgz')
  const directory = path.join(root, location)
  const files = readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter(entry => entry.isFile())
    .map(entry => path.relative(directory, path.join(entry.parentPath, entry.name)).replaceAll('\\', '/'))
  assert.deepEqual(files.sort(), Object.keys(hashes).sort(), 'Unexpected package files')
  for (const [file, sha256] of Object.entries(hashes)) {
    assert.equal(createHash('sha256').update(readFileSync(path.join(directory, file))).digest('hex'), sha256,
      `Unreviewed picomatch bytes: ${location}/${file}`)
  }
}

// Run each potentially exponential match in a disposable process. A vulnerable
// regression must fail by timeout, never hang the audit runner's event loop.
const attacks = [
  ['+(*)b', false], ['+(*a)', false], ['*(*)b', false], ['*(a*)b', false],
  ['+(a*)b', false], ['+(@(*a))', false], ['+(*a?)', true],
  ['+(*[ab])', false], ['+(*{a,b})', false], ['+(*a/*b)', false],
]
let attackChecks = 0
for (const [location] of copies) {
  for (const [pattern, expected] of attacks) {
    const source = `const assert = require('node:assert/strict');
      const pm = require(${JSON.stringify(path.join(root, location))});
      for (const options of [{}, {fastpaths:false}, {capture:true}, {dot:true}, {windows:true}]) {
        assert.equal(pm(${JSON.stringify(pattern)}, options)('a'.repeat(80) + '!'), ${expected});
      }`
    const child = spawnSync(process.execPath, ['-e', source], {
      encoding: 'utf8', timeout: 2000, maxBuffer: 16384,
    })
    assert.ifError(child.error)
    assert.equal(child.status, 0, `${pattern}: ${child.stderr}`)
    attackChecks += 5
  }
}

const pm = require('picomatch')
const compatibility = [
  ['src/**/*.tsx', 'src/components/home.tsx', true],
  ['src/**/*.{ts,tsx}', 'src/api/ai-intent.ts', true],
  ['**/*.css', 'src/styles/main.css', true],
  ['**/node_modules/**', '/app/node_modules/react/index.js', true],
  ['**/node_modules/**', '/app/src/main.tsx', false],
  ['**/*.js', 'src/main.tsx', false],
  ['**/*.ts', '.hidden/file.ts', false],
  ['*.js', 'file.js.map', false],
  ['**/*.ts', 'src/комната.ts', true],
  ['**/*.ts', 'src/habitación.ts', true],
  ['+(a|b)', 'abba', true],
  ['+(*(a)|*(b))', 'abba', true],
  ['\\*', '*', true],
  ['"*"', '*', true],
  ['+(*a)', 'aaaa', true],
  ['+(*)', 'anything', true],
]
for (const [pattern, input, expected] of compatibility) {
  assert.equal(pm(pattern)(input), expected, `${pattern}: ${input}`)
}
assert.equal(pm.scan('src/**/*.tsx').base, 'src')
assert.equal(pm.makeRe('*.js').test('file.js'), true)
assert.equal(typeof pm.parse('*.js').output, 'string')
console.log(JSON.stringify({ picomatchSecurity: 'PASS', copies: copies.length, attackChecks,
  compatibilityChecks: compatibility.length + 3, pinnedSource: '3ab5a7627d480259e3d9ca67fbc14c125d374f0e' }))
