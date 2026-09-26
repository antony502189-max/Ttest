import { expect, type APIRequestContext } from '@playwright/test'
import { deflateSync } from 'node:zlib'

function crc32(data: Buffer) {
  let crc = 0xffffffff
  for (const byte of data) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1))
  }
  return (crc ^ 0xffffffff) >>> 0
}

function pngChunk(type: string, data: Buffer) {
  const name = Buffer.from(type, 'ascii')
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length)
  const checksum = Buffer.alloc(4)
  checksum.writeUInt32BE(crc32(Buffer.concat([name, data])))
  return Buffer.concat([length, name, data, checksum])
}

function seedNumber(seed: string) {
  let value = 2166136261
  for (const char of seed) {
    value ^= char.charCodeAt(0)
    value = Math.imul(value, 16777619)
  }
  return value >>> 0
}

function listingTestPng(seed: string, imageIndex: number) {
  const width = 8
  const height = 8
  const raw = Buffer.alloc((width * 3 + 1) * height)
  let state = (seedNumber(seed) ^ Math.imul(imageIndex + 1, 0x9e3779b1)) >>> 0
  for (let y = 0; y < height; y += 1) {
    const row = y * (width * 3 + 1)
    raw[row] = 0
    for (let x = 0; x < width; x += 1) {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0
      const offset = row + 1 + x * 3
      raw[offset] = state & 0xff
      raw[offset + 1] = (state >>> 8) & 0xff
      raw[offset + 2] = (state >>> 16) & 0xff
    }
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8
  ihdr[9] = 2
  return Buffer.concat([
    Buffer.from('89504e470d0a1a0a', 'hex'),
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', deflateSync(raw)),
    pngChunk('IEND', Buffer.alloc(0)),
  ])
}

export async function uploadRequiredListingPhotos(api: APIRequestContext, token: string, seed: string) {
  const assetIds: string[] = []
  for (let index = 0; index < 5; index += 1) {
    const uploaded = await api.post('/api/v1/uploads', {
      headers: { Authorization: `Bearer ${token}` },
      multipart: {
        file: {
          name: `listing-fixture-${index}.png`,
          mimeType: 'image/png',
          buffer: listingTestPng(seed, index),
        },
      },
    })
    expect(uploaded.status()).toBe(201)
    const body = await uploaded.json() as { id: string }
    assetIds.push(body.id)
  }
  return assetIds
}
