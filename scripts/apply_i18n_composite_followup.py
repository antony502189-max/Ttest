from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = Path(path)
    text = target.read_text()
    if text.count(old) < count:
        raise SystemExit(f"{path}: patch anchor not found: {old[:120]!r}")
    target.write_text(text.replace(old, new, count))


# React splits interpolated children into separate text nodes. Build the user-facing
# sentence first so the i18n layer sees one complete source string.
replace(
    "src/components/marketplace.tsx",
    "  const { discardListing } = useApp();\n  const [imageIndex, setImageIndex] = useState(0);",
    "  const { discardListing } = useApp();\n  const { t } = useI18n();\n  const [imageIndex, setImageIndex] = useState(0);",
)
replace(
    "src/components/marketplace.tsx",
    '<span>{listing.currentResidents} residentes · {listing.roomSizeM2 == null ? unknownListingFact : `${listing.roomSizeM2} m²`}</span>',
    '<span>{t(`${listing.currentResidents} residentes · ${listing.roomSizeM2 == null ? unknownListingFact : `${listing.roomSizeM2} m²`}`)}</span>',
)
replace(
    "src/components/marketplace.tsx",
    '<Badge variant="secondary">+{criticalRestrictions.length - visibleRestrictions.length} condiciones</Badge>',
    '<Badge variant="secondary">{t(`+${criticalRestrictions.length - visibleRestrictions.length} condiciones`)}</Badge>',
)

replace(
    "src/pages/SearchPage.tsx",
    'import { useApp } from "@/contexts/app-context";\n',
    'import { useApp } from "@/contexts/app-context";\nimport { useI18n } from "@/contexts/i18n-context";\n',
)
replace(
    "src/pages/SearchPage.tsx",
    'export function SearchPage() {\n  const [params, setParams] = useSearchParams();',
    'export function SearchPage() {\n  const { t } = useI18n();\n  const [params, setParams] = useSearchParams();',
)
replace(
    "src/pages/SearchPage.tsx",
    '''              <h1 id="results-title">
                {items.length}{" "}
                {items.length === 1 ? "habitación" : "habitaciones"} en{" "}
                {query || "Tenerife"}
              </h1>''',
    '''              <h1 id="results-title">
                {t(`${items.length} ${items.length === 1 ? "habitación" : "habitaciones"} en ${query || "Tenerife"}`)}
              </h1>''',
)

# Cover the singular result heading too.
i18n = Path("src/contexts/i18n-context.tsx")
text = i18n.read_text()
anchor = "  if ((match = source.match(/^(\\d+) habitaciones en (.+)$/))) return target(`${match[1]} комнат в ${match[2]}`, `${match[1]} rooms in ${match[2]}`)\n"
if anchor not in text:
    raise SystemExit("plural search-heading translation anchor not found")
text = text.replace(
    anchor,
    "  if ((match = source.match(/^(\\d+) habitación en (.+)$/))) return target(`${match[1]} комната в ${match[2]}`, `${match[1]} room in ${match[2]}`)\n" + anchor,
    1,
)
i18n.write_text(text)

print("composite i18n follow-up applied")
