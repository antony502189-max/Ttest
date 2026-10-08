"""Sanitized markup matching public Pisos detail galleries inspected 2026-10-08."""

import asyncio

import pytest

from app.external_sources import PisosSource
from app.services.external_import import listing_from_snapshot, normalized_snapshot


def gallery_document(photos: list[str], *, expected: int | None = None) -> str:
    counter = '' if expected is None else f'<span class="js-photosCounter">1</span>/{expected}'
    return (
        counter + '<div class="details__col-left js-desktop"><div class="masonry__list">'
        + ''.join(
            '<div class="masonry__item" data-media-type="Photo"><div class="masonry__content media-thumbnail">'
            f'<picture><img {"src" if index == 0 else "data-src"}="{url}"></picture></div></div>'
            for index, url in enumerate(photos)
        )
        + '</div></div>'
    )


@pytest.mark.parametrize('count', [1, 9, 21])
def test_pisos_own_photos_keep_order_cap_and_published_high_resolution_cover(count):
    source = PisosSource()
    source.scope_key = 'province:Madrid'
    photos = [f'https://fotos.imghs.net/fchm-wp/1010/date/own-{index}.jpg' for index in range(count)]
    cover = photos[0].replace('/fchm-wp/', '/xl-wp/')
    document = (
        f'<meta property="og:image" content="{cover}">'
        '<img src="https://fotos.imghs.net/prof-wp/logos/owner.jpg">'
        + gallery_document([*photos, photos[0].replace('/fchm-wp/', '/apps-wp/')], expected=count)
        + '<div class="related-cards"><img src="https://fotos.imghs.net/fchm-wp/1010/date/other.jpg"></div>'
    )
    parsed = source.parse_listing(document, 'https://www.pisos.com/alquilar/apartamento-madrid-123456/')
    assert parsed['images'] == [cover, *photos[1:]][:15]
    assert parsed['photos_complete'] is True
    normalized = source.normalize_listing({**parsed, 'title': 'Apartamento en alquiler',
        'description': 'Apartamento de un dormitorio', 'property_type': 'apartment', 'bedroom_count': 1,
        'price_text': '900 €/mes', 'city': 'Madrid', 'province': 'Madrid', 'country': 'ES'},
        'https://www.pisos.com/alquilar/apartamento-madrid-123456/')
    assert normalized is not None
    assert normalized.photos == parsed['images']
    assert listing_from_snapshot(normalized_snapshot(normalized)).photos == normalized.photos
    asyncio.run(source.close())


def test_pisos_unrelated_and_untrusted_images_cannot_enter_primary_gallery():
    source = PisosSource()
    cover = 'https://fotos.imghs.net/xl-wp/1010/date/cover.jpg'
    document = (
        f'<meta property="og:image" content="{cover}">'
        + gallery_document([
            'http://fotos.imghs.net/fch-wp/1010/date/http.jpg',
            'https://fotos.imghs.net.evil.test/fch-wp/1010/date/wrong-host.jpg',
            'https://user@fotos.imghs.net/fch-wp/1010/date/credentials.jpg',
            'https://fotos.imghs.net/prof-wp/logos/logo.jpg',
        ], expected=4)
        + '<div class="masonry__list"><div class="media-thumbnail">'
        '<img src="https://fotos.imghs.net/fch-wp/1010/date/uncontained.jpg"></div></div>'
    )
    parsed = source.parse_listing(document, 'https://www.pisos.com/alquilar/piso-madrid-123456/')
    assert parsed['images'] == [cover]
    assert parsed['photos_complete'] is False
    asyncio.run(source.close())


def test_pisos_partial_gallery_is_marked_and_snapshot_retains_incompleteness():
    source = PisosSource()
    source.scope_key = 'province:Madrid'
    photo = 'https://fotos.imghs.net/fch-wp/1010/date/first.jpg'
    parsed = source.parse_listing(gallery_document([photo], expected=9),
        'https://www.pisos.com/alquilar/apartamento-madrid-123456/')
    assert parsed['photos_complete'] is False
    normalized = source.normalize_listing({**parsed, 'title': 'Apartamento en alquiler',
        'description': 'Apartamento de un dormitorio', 'property_type': 'apartment', 'bedroom_count': 1,
        'price_text': '900 €/mes', 'city': 'Madrid', 'province': 'Madrid', 'country': 'ES'},
        'https://www.pisos.com/alquilar/apartamento-madrid-123456/')
    assert normalized is not None
    assert normalized.photos_complete is False
    assert listing_from_snapshot(normalized_snapshot(normalized)).photos_complete is False
    asyncio.run(source.close())


@pytest.mark.parametrize('expected,complete', [(9, True), (10, False)])
def test_published_counter_can_include_a_repeated_cover_without_losing_unique_photos(expected, complete):
    source = PisosSource()
    source.scope_key = 'province:Alicante:holiday'
    # Torrevieja's own masonry contains eight photos plus its repeated cover;
    # the displayed counter counts all nine entries. Missing entries must
    # still keep reconciliation deferred.
    photos = [f'https://fotos.imghs.net/fchm-wp/524316/date/own-{index}.jpg' for index in range(8)]
    document = gallery_document([*photos, photos[0].replace('/fchm-wp/', '/apps-wp/')], expected=expected)
    try:
        parsed = source.parse_listing(document, 'https://www.pisos.com/alquilar/apartamento-playa_del_cura-123456/')
        assert parsed['images'] == photos
        assert parsed['photos_complete'] is complete
        normalized = source.normalize_listing({**parsed, 'title': 'Apartamento en alquiler vacacional',
            'description': 'Apartamento de un dormitorio', 'property_type': 'apartment', 'bedroom_count': 1,
            'price_text': '700 €/sem', 'city': 'Torrevieja', 'province': 'Alicante', 'country': 'ES'}, parsed['url'])
        assert normalized and normalized.photos_complete is complete
        assert listing_from_snapshot(normalized_snapshot(normalized)).photos_complete is complete
    finally:
        asyncio.run(source.close())


@pytest.mark.parametrize('document', ['', gallery_document([]), gallery_document([], expected=0)])
def test_pisos_empty_photo_response_is_partial_in_normalized_and_persisted_snapshots(document):
    source = PisosSource()
    source.scope_key = 'province:Madrid'
    url = 'https://www.pisos.com/alquilar/apartamento-madrid-123456/'
    parsed = source.parse_listing(document, url)
    assert parsed['images'] == []
    assert parsed['photos_complete'] is False
    normalized = source.normalize_listing({**parsed, 'title': 'Apartamento en alquiler',
        'description': 'Apartamento de un dormitorio', 'property_type': 'apartment', 'bedroom_count': 1,
        'price_text': '900 €/mes', 'city': 'Madrid', 'province': 'Madrid', 'country': 'ES'}, url)
    assert normalized is not None
    assert normalized.photos == []
    assert normalized.photos_complete is False
    assert listing_from_snapshot(normalized_snapshot(normalized)).photos_complete is False
    asyncio.run(source.close())
