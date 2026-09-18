import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { containsBlockedListingLink } from '../src/lib/listing-content-safety'

test('listing link detector catches direct and obfuscated destinations', () => {
  const blocked = [
    'https://evil.example/path',
    'hxxp://evil.com/login',
    'h t t p s : / / evil.com',
    'www.evil.com',
    'evil.com/path',
    'evil[.]com',
    'evil(.)com',
    'evil[dot]com',
    'evil dot com',
    'evil punto es',
    'evil . com',
    'https%3A%2F%2Fevil.com',
    'evil&#46;com',
    'evil。com',
    'ev\u200bil.com',
    '127.0.0.1:8080',
    '[2001:db8::1]',
    'пример.рф',
    'xn--e1afmkfd.xn--p1ai',
    'javascript:alert(1)',
    'data:text/html,test',
    'mailto:someone@example.com',
    'tel:+34900123456',
    'sms:+34900123456',
    'magnet:?xt=urn:btih:deadbeef',
    'ipfs://bafybeigdyrzt/path',
    'tg://resolve?domain=example',
    'https%253A%252F%252Fevil.com',
    'ｈｔｔｐｓ：／／ｅｖｉｌ．ｃｏｍ',
    'h\u200btt\u200bps://evil.com',
    'login.secure.evil.xyz/reset',
    'evil{dot}com',
    'evil [ . ] com',
    'user@evil.com',
    'evil.com:8443/login',
  ]
  for (const value of blocked) expect(containsBlockedListingLink(value), value).toBe(true)
})

test('listing link detector leaves normal property prose alone', () => {
  const allowed = [
    'Piso amplio. Cocina reformada y Wi-Fi incluido.',
    'La habitación mide 12.5 m² y está a 5 min. del tranvía.',
    'Contacta mediante los botones de teléfono o WhatsApp del anuncio.',
    'Incluye 100 €/mes de gastos.',
    'Dr. House es la referencia del propietario.',
    'p. ej. cerca del tranvía',
  ]
  for (const value of allowed) expect(containsBlockedListingLink(value), value).toBe(false)
})

test('create and edit forms enforce the same link-free public text policy', () => {
  const publish = readFileSync('src/pages/PublishPage.tsx', 'utf8')
  const edit = readFileSync('src/pages/ListingEditPage.tsx', 'utf8')

  for (const source of [publish, edit]) {
    expect(source).toContain('containsBlockedListingLink(draft.area)')
    expect(source).toContain('containsBlockedListingLink(draft.rules)')
    expect(source).toContain('containsBlockedListingLink(draft.title)')
    expect(source).toContain('containsBlockedListingLink(draft.description)')
    expect(source).toContain('listingLinkBlockedMessage')
  }
})
