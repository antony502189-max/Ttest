const schemePattern = /\b(?:h\s*[tx]\s*[tx]\s*p\s*s?|f\s*t\s*p|javascript|data|vbscript|file|mailto|tel|sms|magnet|intent|market|blob)\s*:\s*(?:[\\/]\s*){0,2}/iu
const genericUriPattern = /\b[a-z][a-z0-9+.-]{1,31}\s*:\s*(?:[\\/]\s*){2}/iu
const wwwPattern = /\bw\s*w\s*w\s*(?:\.|\[\s*(?:\.|dot|punto)\s*\]|\(\s*(?:\.|dot|punto)\s*\)|\{\s*(?:\.|dot|punto)\s*\})/iu
const directDomainPattern = /(?:^|[^\p{L}\p{N}_-])(?:[\p{L}\p{N}](?:[\p{L}\p{N}-]{0,61}[\p{L}\p{N}])?\.)+(?:xn--[a-z0-9-]{2,59}|\p{L}{2,63})(?=$|[^\p{L}\p{N}_-])/iu
const obfuscatedDomainPattern = /(?:^|[^\p{L}\p{N}_-])[\p{L}\p{N}][\p{L}\p{N}-]{0,62}\s*(?:\[\s*(?:\.|dot|punto)\s*\]|\(\s*(?:\.|dot|punto)\s*\)|\{\s*(?:\.|dot|punto)\s*\}|\s+\.\s+|\s+(?:dot|punto)\s+)\s*(?:com|org|net|es|info|biz|xyz|top|site|online|live|shop|club|click|link|work|cloud|app|dev|io|co|me|ru|tk|ml|ga|cf|gq|zip|mov|cc|su|eu|uk|de|fr|nl|se|no|it|pt|pl|ua|by|ly|ai|pro|tv|pw|ws|mobi|name|tech|store|space|website|world|today|gg|to|ph|in|us|ca|au)\b/iu
const ipv4Pattern = /(?:^|[^\d.])((?:\d{1,3}\s*\.\s*){3}\d{1,3})(?::\d{1,5})?(?![\d.])/gu
const ipv6Pattern = /\[[0-9a-f:]{2,}\](?::\d{1,5})?/iu

export const listingLinkBlockedMessage = 'No se permiten enlaces, dominios ni direcciones web en los anuncios.'

function decodeEntities(value: string) {
  return value
    .replace(/&(period|#0*46|#x0*2e);/gi, '.')
    .replace(/&(colon|#0*58|#x0*3a);/gi, ':')
    .replace(/&(sol|#0*47|#x0*2f);/gi, '/')
}

function decodePercentEncoding(value: string) {
  let current = value
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const decoded = decodeURIComponent(current)
      if (decoded === current) break
      current = decoded
    } catch {
      break
    }
  }
  return current
}

function normalizeForLinkCheck(value: string) {
  return decodePercentEncoding(decodeEntities(value))
    .normalize('NFKC')
    .replace(/[。．｡․﹒]/gu, '.')
    .replace(/\p{Cf}/gu, '')
    .toLowerCase()
}

function containsIpv4(value: string) {
  for (const match of value.matchAll(ipv4Pattern)) {
    const candidate = match[1].replace(/\s+/g, '')
    const octets = candidate.split('.').map(Number)
    if (octets.length === 4 && octets.every((octet) => Number.isInteger(octet) && octet >= 0 && octet <= 255)) return true
  }
  return false
}

export function containsBlockedListingLink(value: string) {
  if (!value) return false
  const normalized = normalizeForLinkCheck(value)
  return schemePattern.test(normalized)
    || genericUriPattern.test(normalized)
    || wwwPattern.test(normalized)
    || directDomainPattern.test(normalized)
    || obfuscatedDomainPattern.test(normalized)
    || containsIpv4(normalized)
    || ipv6Pattern.test(normalized)
}
