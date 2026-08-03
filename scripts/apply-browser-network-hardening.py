from pathlib import Path


SOURCE = Path("backend/app/external_sources.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one exact match, found {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from .core.config import get_settings\n",
        "from .core.browser_network import (\n"
        "    configure_public_browser_context,\n"
        "    hostname_matches_domain,\n"
        "    validate_public_browser_url,\n"
        ")\n"
        "from .core.config import get_settings\n",
    )
    text = replace_once(
        text,
        '                    context_options: dict[str, Any] = {"locale": "es-ES"}\n',
        '                    context_options: dict[str, Any] = {\n'
        '                        "locale": "es-ES",\n'
        '                        "service_workers": "block",\n'
        '                        "accept_downloads": False,\n'
        '                    }\n',
    )
    text = replace_once(
        text,
        "                    self._browser_context = await self._browser.new_context(**context_options)\n"
        "                page = await self._browser_context.new_page()\n",
        "                    self._browser_context = await self._browser.new_context(**context_options)\n"
        "                    await configure_public_browser_context(self._browser_context)\n"
        "                page = await self._browser_context.new_page()\n",
    )
    text = replace_once(
        text,
        "        try:\n"
        "            async with self._browser_lock:\n",
        "        try:\n"
        "            if not hostname_matches_domain(url, self.domain):\n"
        "                return None\n"
        "            await validate_public_browser_url(url)\n"
        "            async with self._browser_lock:\n",
    )
    text = replace_once(
        text,
        "                    final_url = page.url\n"
        "                    self._record_page(url, document, status=status, final_url=final_url, method=\"BROWSER_GET\")\n",
        "                    final_url = page.url\n"
        "                    await validate_public_browser_url(final_url)\n"
        "                    if not hostname_matches_domain(final_url, self.domain):\n"
        "                        return None\n"
        "                    self._record_page(url, document, status=status, final_url=final_url, method=\"BROWSER_GET\")\n",
    )
    text = replace_once(
        text,
        "        except (OSError, PlaywrightError, PlaywrightTimeoutError):\n",
        "        except (OSError, httpx.HTTPError, PlaywrightError, PlaywrightTimeoutError, ValueError):\n",
    )
    text = replace_once(
        text,
        "            parsed.netloc.endswith(self.domain)\n"
        "            and url.rstrip(\"/\") not in {discovery.rstrip(\"/\") for discovery in self.discovery_urls}\n",
        "            parsed.scheme in {\"http\", \"https\"}\n"
        "            and hostname_matches_domain(url, self.domain)\n"
        "            and url.rstrip(\"/\") not in {discovery.rstrip(\"/\") for discovery in self.discovery_urls}\n",
    )
    text = replace_once(
        text,
        "        return parsed.netloc.endswith(self.domain) and bool(\n",
        "        return parsed.scheme in {\"http\", \"https\"} and hostname_matches_domain(url, self.domain) and bool(\n",
    )
    SOURCE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
