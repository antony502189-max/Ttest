from __future__ import annotations

import html
import ipaddress
import re
import unicodedata
from urllib.parse import unquote

_DOT_TRANSLATION = str.maketrans({
    "。": ".",
    "．": ".",
    "｡": ".",
    "․": ".",
    "﹒": ".",
})

_SCHEME_RE = re.compile(
    r"(?ixu)\b(?:h\s*[tx]\s*[tx]\s*p\s*s?|f\s*t\s*p|javascript|data|vbscript|file|mailto|"
    r"tel|sms|magnet|intent|market|blob)\s*:\s*(?:[\\/]\s*){0,2}"
)
_GENERIC_URI_RE = re.compile(r"(?iu)\b[a-z][a-z0-9+.-]{1,31}\s*:\s*(?:[\\/]\s*){2}")
_WWW_RE = re.compile(
    r"(?ixu)\bw\s*w\s*w\s*(?:\.|\[\s*(?:\.|dot|punto)\s*\]|"
    r"\(\s*(?:\.|dot|punto)\s*\)|\{\s*(?:\.|dot|punto)\s*\})"
)
_DIRECT_DOMAIN_RE = re.compile(
    r"(?iu)(?<![\w-])(?:[^\W_](?:[\w-]{0,61}[^\W_])?\.)+"
    r"(?:xn--[a-z0-9-]{2,59}|[^\W\d_]{2,63})(?=$|[^\w-])"
)
_OBFUSCATED_DOMAIN_RE = re.compile(
    r"(?ixu)(?<![\w-])[\w][\w-]{0,62}\s*"
    r"(?:"
    r"\[\s*(?:\.|dot|punto)\s*\]|"
    r"\(\s*(?:\.|dot|punto)\s*\)|"
    r"\{\s*(?:\.|dot|punto)\s*\}|"
    r"\s+\.\s+|"
    r"\s+(?:dot|punto)\s+"
    r")\s*"
    r"(?:com|org|net|es|info|biz|xyz|top|site|online|live|shop|club|click|link|work|cloud|"
    r"app|dev|io|co|me|ru|tk|ml|ga|cf|gq|zip|mov|cc|su|eu|uk|de|fr|nl|se|no|it|pt|pl|"
    r"ua|by|ly|ai|pro|tv|pw|ws|mobi|name|tech|store|space|website|world|today|gg|to|ph|"
    r"in|us|ca|au)\b"
)
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\s*\.\s*){3}\d{1,3}(?::\d{1,5})?(?![\d.])")
_IPV6_RE = re.compile(r"\[([0-9a-f:]{2,})\](?::\d{1,5})?", re.IGNORECASE)


def _normalize_for_link_check(value: str) -> str:
    normalized = html.unescape(value)
    for _ in range(2):
        decoded = unquote(normalized)
        if decoded == normalized:
            break
        normalized = decoded
    normalized = unicodedata.normalize("NFKC", normalized).translate(_DOT_TRANSLATION)
    normalized = "".join(character for character in normalized if unicodedata.category(character) != "Cf")
    return normalized.casefold()


def _contains_ip_address(value: str) -> bool:
    for match in _IPV4_RE.finditer(value):
        candidate = re.sub(r"\s+", "", match.group(0)).split(":", 1)[0]
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return True

    for match in _IPV6_RE.finditer(value):
        try:
            ipaddress.ip_address(match.group(1))
        except ValueError:
            continue
        return True
    return False


def contains_listing_link(value: str) -> bool:
    """Return True when user-authored listing text contains URL-like content.

    The product policy is intentionally stricter than a reputation service:
    public listing prose is link-free. Normalization catches common attempts
    to hide destinations with Unicode, percent encoding, zero-width characters,
    hxxp, spaced protocols, bracketed dots, or raw IP addresses.
    """

    if not value:
        return False
    normalized = _normalize_for_link_check(value)
    return bool(
        _SCHEME_RE.search(normalized)
        or _GENERIC_URI_RE.search(normalized)
        or _WWW_RE.search(normalized)
        or _DIRECT_DOMAIN_RE.search(normalized)
        or _OBFUSCATED_DOMAIN_RE.search(normalized)
        or _contains_ip_address(normalized)
    )
