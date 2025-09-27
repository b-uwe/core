"""Test Music Favorites MusicBrainz client functionality."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.components.music_favorites.musicbrainz import (
    MusicBrainzClient,
    MusicBrainzError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .fixtures.musicbrainz_responses import IRON_MAIDEN_COMPLETE_RESPONSE


@pytest.fixture
async def musicbrainz_client(hass: HomeAssistant) -> MusicBrainzClient:
    """Create a MusicBrainz client instance."""
    return MusicBrainzClient(hass)


async def test_search_artists_success(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test successful artist search."""
    mock_response_data = {
        "artists": [
            {
                "id": "f0d05c64-9959-4ae1-899b-acf51b97638c",
                "name": "Dyscarnate",
                "disambiguation": "British metal band",
                "score": 100,
            },
            {
                "id": "test-id-2",
                "name": "Dyscarnate",
                "disambiguation": "Different band",
                "score": 85,
            },
        ]
    }

    # Mock the aiohttp session response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("Dyscarnate")

    assert len(result) == 2
    assert result[0]["id"] == "f0d05c64-9959-4ae1-899b-acf51b97638c"
    assert result[0]["name"] == "Dyscarnate"
    assert result[0]["disambiguation"] == "British metal band"
    assert result[0]["score"] == 100
    assert result[1]["score"] == 85


async def test_search_artists_custom_limit(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with custom limit."""
    mock_response_data = {"artists": []}
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("TestBand", limit=5)

    assert result == []


async def test_search_artists_no_results(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with no results."""
    mock_response_data = {"artists": []}
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("NonExistentBand")

    assert result == []


async def test_search_artists_missing_fields(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with missing optional fields."""
    mock_response_data = {
        "artists": [
            {
                "id": "test-id-1",
                "name": "Minimal Band",
                # Missing disambiguation and score fields
            }
        ]
    }
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("Minimal Band")

    assert len(result) == 1
    assert result[0]["id"] == "test-id-1"
    assert result[0]["name"] == "Minimal Band"
    assert result[0]["disambiguation"] == ""
    assert result[0]["score"] == 0


async def test_search_artists_http_error(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with HTTP error."""
    mock_response = AsyncMock()
    mock_response.status = 500

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(
            MusicBrainzError, match="MusicBrainz API returned status 500"
        ):
            await musicbrainz_client.search_artists("TestBand")


async def test_search_artists_client_error(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with aiohttp client error."""
    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.side_effect = aiohttp.ClientError("Connection failed")

        with pytest.raises(
            MusicBrainzError, match="MusicBrainz search failed: Connection failed"
        ):
            await musicbrainz_client.search_artists("TestBand")


async def test_search_artists_json_error(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with JSON decode error."""
    mock_response = AsyncMock()
    mock_response.status = 200
    # Use a more generic ClientError instead of ContentTypeError
    mock_response.json.side_effect = aiohttp.ClientError("Invalid JSON")

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(MusicBrainzError, match="MusicBrainz search failed:"):
            await musicbrainz_client.search_artists("TestBand")


async def test_musicbrainz_error_inheritance() -> None:
    """Test that MusicBrainzError inherits from HomeAssistantError."""
    error = MusicBrainzError("Test error")
    assert isinstance(error, HomeAssistantError)
    assert str(error) == "Test error"


async def test_client_initialization(hass: HomeAssistant) -> None:
    """Test MusicBrainz client initialization."""
    client = MusicBrainzClient(hass)
    assert client.hass is hass
    assert client.session is not None


async def test_search_artists_empty_response(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search with empty response."""
    mock_response_data = {}  # No "artists" key
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("TestBand")

    assert result == []


async def test_search_artists_with_aliases(
    hass: HomeAssistant, musicbrainz_client: MusicBrainzClient
) -> None:
    """Test artist search includes aliases in results."""
    # Use realistic MusicBrainz response data from fixtures
    mock_response_data = {"artists": [IRON_MAIDEN_COMPLETE_RESPONSE]}
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = mock_response_data

    with patch.object(musicbrainz_client.session, "get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await musicbrainz_client.search_artists("Iron Maiden")

    assert len(result) == 1
    artist = result[0]
    assert artist["id"] == "ca891d65-d9b0-4258-89f7-e6ba29d83767"
    assert artist["name"] == "Iron Maiden"
    assert artist["aliases"] == [
        "Ironmaiden",
        "Maiden",
        "鉄の処女",
    ]  # Real aliases from fixture
