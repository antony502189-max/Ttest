import asyncio
import json

import httpx
import pytest

from app.external_sources import PisosSource

ROOT = 'https://www.pisos.com/alquiler/pisos-madrid/'


def test_bounded_discovery_resumes_provider_pagination_without_repeating_first_pages():
    async def verify():
        calls = []
        checkpoint = None
        for index in range(3):
            source = PisosSource()
            source.discovery_urls = (ROOT,)
            source.max_discovery_pages = 1
            source.resumable_discovery = True
            source.discovery_checkpoint = checkpoint

            async def request(url):
                calls.append(url)
                page = 1 if url == ROOT else int(url.rstrip('/').rsplit('/', 1)[1])
                links = f'<a href="/alquilar/piso-madrid-{100000 + page}/">detail</a>'
                links += ''.join(f'<a href="{ROOT}{n}/">page</a>' for n in range(2, 4))
                return links

            source.request = request
            discovery = await source.discover_listing_urls()
            assert discovery.visited_pages == 1
            assert len(discovery.urls) == 1
            assert not discovery.complete
            checkpoint = json.loads(json.dumps(discovery.continuation))
            assert bool(checkpoint) == (index < 2)
            await source.close()
        assert calls == [ROOT, ROOT + '2/', ROOT + '3/']
    asyncio.run(verify())


def test_temporary_page_failure_retains_retry_cursor_and_partial_semantics():
    async def verify():
        source = PisosSource()
        source.discovery_urls = (ROOT,)
        source.max_discovery_pages = 1
        source.resumable_discovery = True

        async def unavailable(url):
            raise httpx.ReadTimeout('temporary')

        source.request = unavailable
        result = await source.discover_listing_urls()
        assert not result.complete
        assert result.failed_pages == [ROOT]
        assert result.continuation['pending'] == [[ROOT, ROOT]]
        assert result.continuation['visited'] == []
        await source.close()
    asyncio.run(verify())


def test_checkpoint_cannot_change_provider_or_scope_routes():
    async def verify():
        source = PisosSource()
        source.discovery_urls = (ROOT,)
        source.resumable_discovery = True
        source.discovery_checkpoint = {'version': 1, 'routes': [ROOT],
            'pending': [['https://other.test/2/', ROOT]], 'visited': []}
        with pytest.raises(ValueError, match='escaped'):
            await source.discover_listing_urls()
        source.discovery_checkpoint['routes'] = [ROOT + 'different/']
        with pytest.raises(ValueError, match='routes changed'):
            await source.discover_listing_urls()
        await source.close()
    asyncio.run(verify())
