"""Tests for the ldjson module."""

from __future__ import annotations

import json

import aiohttp
import pytest

from homeassistant.components.music_favorites.ldjson import (
    LdJsonError,
    fetch_and_extract_ldjson,
)
from homeassistant.core import HomeAssistant

from .fixtures.bandsintown_responses import MIXED_LDJSON_DATA, VULVODYNIA_EVENTS_LDJSON

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_html_with_real_ldjson():
    """Sample HTML containing real Bandsintown LD+JSON data."""
    # Create HTML with realistic Bandsintown LD+JSON scripts
    vulvodynia_event_json = json.dumps(VULVODYNIA_EVENTS_LDJSON[0], indent=2)
    mixed_data_json = json.dumps(MIXED_LDJSON_DATA, indent=2)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {vulvodynia_event_json}
        </script>
        <script type="application/ld+json">
        {mixed_data_json}
        </script>
    </head>
    <body>
        <p>Bandsintown page content</p>
    </body>
    </html>
    """


@pytest.fixture
def mock_html_no_ldjson():
    """Sample HTML without LD+JSON scripts."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript">
        console.log("Regular script");
        </script>
    </head>
    <body>
        <p>No LD+JSON here</p>
    </body>
    </html>
    """


@pytest.fixture
def mock_html_invalid_json():
    """Sample HTML with invalid JSON in LD+JSON script."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@type": "MusicEvent",
            "name": "Invalid JSON",
            "startDate": // Invalid comment
        }
        </script>
        <script type="application/ld+json">
        {
            "@type": "MusicEvent",
            "name": "Valid Event"
        }
        </script>
    </head>
    </html>
    """


async def test_fetch_and_extract_ldjson_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_html_with_real_ldjson: str,
) -> None:
    """Test successful fetching and extraction of real Bandsintown LD+JSON data."""
    test_url = "https://www.bandsintown.com/a/6461184"

    aioclient_mock.get(test_url, text=mock_html_with_real_ldjson)

    result = await fetch_and_extract_ldjson(hass, test_url)

    # Should extract 5 LD+JSON objects:
    # 1 single event + 4 from mixed array (2 events + 1 band + 1 review)
    assert len(result) == 5

    # Check first object (single Vulvodynia event)
    assert result[0]["@type"] == "MusicEvent"
    assert result[0]["name"] == "Vulvodynia @ O2 Academy Islington"
    assert result[0]["startDate"] == "2025-11-25T18:00:00"

    # Check objects from mixed array - should include all types
    event_types = [obj.get("@type") for obj in result[1:]]
    assert "MusicEvent" in event_types
    assert "MusicGroup" in event_types
    assert "Review" in event_types


async def test_fetch_and_extract_ldjson_no_scripts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_html_no_ldjson: str
) -> None:
    """Test fetching HTML with no LD+JSON scripts."""
    test_url = "https://example.com/no-ldjson"

    aioclient_mock.get(test_url, text=mock_html_no_ldjson)

    result = await fetch_and_extract_ldjson(hass, test_url)

    # Should return empty list when no LD+JSON scripts found
    assert result == []


async def test_fetch_and_extract_ldjson_invalid_json(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_html_invalid_json: str,
) -> None:
    """Test handling of invalid JSON in LD+JSON scripts."""
    test_url = "https://example.com/invalid-json"

    aioclient_mock.get(test_url, text=mock_html_invalid_json)

    result = await fetch_and_extract_ldjson(hass, test_url)

    # Should only extract the valid JSON object, skipping the invalid one
    assert len(result) == 1
    assert result[0]["@type"] == "MusicEvent"
    assert result[0]["name"] == "Valid Event"


async def test_fetch_and_extract_ldjson_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test handling of HTTP errors."""
    test_url = "https://example.com/not-found"

    aioclient_mock.get(test_url, status=404)

    with pytest.raises(LdJsonError, match="HTTP request failed with status 404"):
        await fetch_and_extract_ldjson(hass, test_url)


async def test_fetch_and_extract_ldjson_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test handling of aiohttp client errors."""
    test_url = "https://example.com/connection-error"

    aioclient_mock.get(test_url, exc=aiohttp.ClientError("Connection failed"))

    with pytest.raises(LdJsonError, match="Failed to fetch URL: Connection failed"):
        await fetch_and_extract_ldjson(hass, test_url)


async def test_fetch_and_extract_ldjson_empty_script(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test handling of empty LD+JSON scripts."""
    html_with_empty_script = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json"></script>
        <script type="application/ld+json">   </script>
        <script type="application/ld+json">
        {
            "@type": "MusicEvent",
            "name": "Valid Event"
        }
        </script>
    </head>
    </html>
    """

    test_url = "https://example.com/empty-scripts"

    aioclient_mock.get(test_url, text=html_with_empty_script)

    result = await fetch_and_extract_ldjson(hass, test_url)

    # Should only extract the valid non-empty script
    assert len(result) == 1
    assert result[0]["@type"] == "MusicEvent"
    assert result[0]["name"] == "Valid Event"
