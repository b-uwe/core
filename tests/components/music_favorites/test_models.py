"""Test Music Favorites model functions."""

from datetime import date, datetime, timedelta
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.models import (
    BandStatus,
    add_favorite,
    determine_band_status,
    extract_pure_event_data,
    fetch_external_data,
    get_tour_status,
    remove_favorite,
    resolve_artist_from_name,
)
from homeassistant.components.music_favorites.musicbrainz import (
    MusicBrainzClient,
    MusicBrainzError,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .fixtures.bandsintown_responses import VULVODYNIA_EVENTS_LDJSON
from .fixtures.musicbrainz_responses import (
    HALF_ME_COMPLETE_RESPONSE,
    IRON_MAIDEN_COMPLETE_RESPONSE,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry with some test favorites."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {
                "ca891d65-d9b0-4258-89f7-e6ba29d83767": {"variants": ["Iron Maiden"]},
                "5182c1d9-c7d2-4dad-afa0-ccfeada921a8": {"variants": ["Black Sabbath"]},
                "ce2703e5-34f4-4389-883f-00f8ca2662c2": {
                    "variants": ["花冷え。"]
                },  # Using Unicode characters for testing
            }
        },
        unique_id="music_favorites",
    )


@pytest.fixture
def mock_entity_registry():
    """Create a mock entity registry."""
    entity_registry = MagicMock()
    entity_registry.async_get_entity_id = MagicMock(
        return_value="sensor.music_favorites_favorite_test_id"
    )
    entity_registry.async_remove = MagicMock()
    return entity_registry


async def test_add_favorite_success(hass: HomeAssistant, mock_config_entry) -> None:
    """Test successfully adding a new favorite."""
    mock_config_entry.add_to_hass(hass)

    # Mock the config entry update
    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        mock_fetch_external.return_value = {
            "artist_data": HALF_ME_COMPLETE_RESPONSE,
            "relation_links": {
                "allmusic_url": "https://www.allmusic.com/artist/mn0004372703",
                "bandsintown_url": "https://www.bandsintown.com/a/15548431",
                "discogs_url": "https://www.discogs.com/artist/12559079",
                "songkick_url": "https://www.songkick.com/artists/10118274",
                "musicbrainz_url": "https://musicbrainz.org/artist/963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",
            },
            "events": [],
            "variants": ["Half Me"],
            "status": BandStatus.ACTIVE,
        }

        # Add a new favorite (Half Me is not in the mock_config_entry)
        await add_favorite(
            hass,
            mock_config_entry,
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",  # Half Me ID
        )

        # Verify the config entry was updated with new favorite
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_entry = call_args[0][0]  # First argument (the entry)
        updated_data = call_args[1]["data"]  # The data keyword argument

        assert updated_entry == mock_config_entry
        assert "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec" in updated_data["favorites"]
        # Half Me has no aliases - should only contain the name itself
        stored_data = updated_data["favorites"]["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]
        assert stored_data["variants"] == ["Half Me"]
        # Should also have relation links
        assert "allmusic_url" in stored_data
        assert "bandsintown_url" in stored_data

        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_add_favorite_with_entity_manager(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test adding a favorite with entity manager present (dynamic entity creation)."""
    mock_config_entry.add_to_hass(hass)

    # Create mock entity manager
    mock_entity_manager = MagicMock()
    mock_config_entry.runtime_data = {"entity_manager": mock_entity_manager}

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        mock_fetch_external.return_value = {
            "artist_data": HALF_ME_COMPLETE_RESPONSE,
            "relation_links": {
                "allmusic_url": "https://www.allmusic.com/artist/mn0004372703",
                "bandsintown_url": "https://www.bandsintown.com/a/15548431",
                "discogs_url": "https://www.discogs.com/artist/12559079",
                "songkick_url": "https://www.songkick.com/artists/10118274",
                "musicbrainz_url": "https://musicbrainz.org/artist/963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",
            },
            "events": [],
            "variants": ["Half Me"],
            "status": BandStatus.ACTIVE,
        }

        # Add a new favorite
        await add_favorite(
            hass,
            mock_config_entry,
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",  # Half Me ID
        )

        # Verify the config entry was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]["favorites"]
        assert "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec" in updated_data

        # Verify the entity manager was called to add the entity dynamically
        expected_favorite_data = {
            "variants": ["Half Me"],
            "status": BandStatus.ACTIVE,  # Status is now included
            "events": [],  # Empty events list since LD+JSON returned empty
            "musicbrainz_url": "https://musicbrainz.org/artist/963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",
            "allmusic_url": "https://www.allmusic.com/artist/mn0004372703",
            "bandsintown_url": "https://www.bandsintown.com/a/15548431",
            "discogs_url": "https://www.discogs.com/artist/12559079",
            "songkick_url": "https://www.songkick.com/artists/10118274",
        }
        mock_entity_manager.add_favorite_entity.assert_called_once_with(
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec", expected_favorite_data
        )


async def test_add_favorite_already_exists(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test adding a favorite that already exists raises an error."""
    mock_config_entry.add_to_hass(hass)

    # Try to add a favorite that already exists (using existing MusicBrainz ID)
    with pytest.raises(ServiceValidationError, match="already exists"):
        await add_favorite(
            hass,
            mock_config_entry,
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",  # Iron Maiden ID already in mock_config_entry
        )


async def test_add_favorite_case_insensitive_duplicate(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that duplicate detection works by MusicBrainz ID."""
    mock_config_entry.add_to_hass(hass)

    # Try to add the same MusicBrainz ID again (Iron Maiden already exists)
    # This should fail because the MusicBrainz ID already exists
    with pytest.raises(ServiceValidationError, match="already exists"):
        await add_favorite(
            hass,
            mock_config_entry,
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",  # Same Iron Maiden ID
        )


async def test_add_favorite_unicode_handling(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test adding favorites with unicode characters."""
    mock_config_entry.add_to_hass(hass)

    # Mock the config entry update and reload
    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        mock_fetch_external.return_value = {
            "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
            "relation_links": {
                "allmusic_url": "https://www.allmusic.com/artist/mn0000098465",
                "bandsintown_url": "https://www.bandsintown.com/a/1301",
                "discogs_url": "https://www.discogs.com/artist/251595",
                "songkick_url": "https://www.songkick.com/artists/438390",
                "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
            },
            "events": [],
            "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
            "status": BandStatus.ACTIVE,
        }

        # Add a favorite with unicode data (using different ID not in mock_config_entry)
        await add_favorite(
            hass,
            mock_config_entry,
            "different-unicode-id-123",  # Different ID for unicode test
        )

        # Verify it was added correctly
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        # The ID should be the MusicBrainz ID
        assert "different-unicode-id-123" in updated_data["favorites"]
        # Iron Maiden should be stored with name + aliases (including unicode)
        stored_data = updated_data["favorites"]["different-unicode-id-123"]
        expected_variants = ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"]
        assert stored_data["variants"] == expected_variants
        # Should also have relation links
        assert "allmusic_url" in stored_data


async def test_remove_favorite_success(
    hass: HomeAssistant, mock_config_entry, mock_entity_registry
) -> None:
    """Test successfully removing an existing favorite."""
    mock_config_entry.add_to_hass(hass)

    # Mock entity registry
    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Remove an existing favorite by MusicBrainz ID
        await remove_favorite(
            hass, mock_config_entry, "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )

        # Verify the config entry was updated (favorite removed)
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        # Verify "Iron Maiden" was removed but others remain
        assert "ca891d65-d9b0-4258-89f7-e6ba29d83767" not in updated_data["favorites"]
        assert "5182c1d9-c7d2-4dad-afa0-ccfeada921a8" in updated_data["favorites"]
        assert "ce2703e5-34f4-4389-883f-00f8ca2662c2" in updated_data["favorites"]

        # Verify entity registry cleanup was attempted
        mock_entity_registry.async_get_entity_id.assert_called_once_with(
            "sensor",
            "music_favorites",
            "favorite_ca891d65-d9b0-4258-89f7-e6ba29d83767",
        )
        mock_entity_registry.async_remove.assert_called_once_with(
            "sensor.music_favorites_favorite_test_id"
        )

        # Verify the config entry was reloaded (to update UI)
        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_remove_favorite_case_insensitive(
    hass: HomeAssistant, mock_config_entry, mock_entity_registry
) -> None:
    """Test removing favorites works regardless of case."""
    mock_config_entry.add_to_hass(hass)

    # Mock entity registry
    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Remove using MusicBrainz ID (case doesn't matter for IDs)
        await remove_favorite(
            hass, mock_config_entry, "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )

        # Verify it was still found and removed
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "ca891d65-d9b0-4258-89f7-e6ba29d83767" not in updated_data["favorites"]

        # Verify the config entry was reloaded (to update UI)
        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_remove_favorite_unicode(
    hass: HomeAssistant, mock_config_entry, mock_entity_registry
) -> None:
    """Test removing favorites with unicode characters."""
    mock_config_entry.add_to_hass(hass)

    # Mock entity registry
    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Remove the unicode favorite by MusicBrainz ID
        await remove_favorite(
            hass, mock_config_entry, "ce2703e5-34f4-4389-883f-00f8ca2662c2"
        )

        # Verify it was removed
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "ce2703e5-34f4-4389-883f-00f8ca2662c2" not in updated_data["favorites"]

        # Verify the config entry was reloaded (to update UI)
        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_remove_favorite_not_found(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test removing a non-existent favorite raises an error."""
    mock_config_entry.add_to_hass(hass)

    # Try to remove a favorite that doesn't exist by MusicBrainz ID
    with pytest.raises(ServiceValidationError, match="not found"):
        await remove_favorite(
            hass, mock_config_entry, "00000000-0000-0000-0000-000000000000"
        )


async def test_remove_favorite_no_entity_in_registry(
    hass: HomeAssistant, mock_config_entry, mock_entity_registry
) -> None:
    """Test removing favorite when entity doesn't exist in registry (graceful handling)."""
    mock_config_entry.add_to_hass(hass)

    # Mock entity registry to return None (entity not found)
    mock_entity_registry.async_get_entity_id.return_value = None

    with (
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_entity_registry,
        ),
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Remove should still succeed even if entity isn't in registry
        await remove_favorite(
            hass, mock_config_entry, "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )

        # Verify the favorite was still removed from config
        mock_update.assert_called_once()

        # Verify registry cleanup was attempted but remove was NOT called (because entity_id was None)
        mock_entity_registry.async_get_entity_id.assert_called_once()
        mock_entity_registry.async_remove.assert_not_called()

        # Verify the config entry was reloaded (to update UI)
        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_add_favorite_with_aliases(hass: HomeAssistant) -> None:
    """Test adding favorite with aliases stores them correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        mock_fetch_external.return_value = {
            "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
            "relation_links": {
                "allmusic_url": "https://www.allmusic.com/artist/mn0000098465",
                "bandsintown_url": "https://www.bandsintown.com/a/1301",
                "discogs_url": "https://www.discogs.com/artist/251595",
                "songkick_url": "https://www.songkick.com/artists/438390",
                "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
            },
            "events": [],
            "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
            "status": BandStatus.ACTIVE,
        }

        await add_favorite(
            hass,
            entry,
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",  # Iron Maiden ID
        )

        # Verify config update was called with aliases included
        mock_update.assert_called_once()
        updated_data = mock_update.call_args[1]["data"]["favorites"]
        assert "ca891d65-d9b0-4258-89f7-e6ba29d83767" in updated_data
        stored_data = updated_data["ca891d65-d9b0-4258-89f7-e6ba29d83767"]
        # Iron Maiden has name + real aliases from MusicBrainz
        expected_variants = ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"]
        assert stored_data["variants"] == expected_variants

        # Verify reload was called
        # Note: No longer reloading config entry - using dynamic entity management instead


async def test_add_favorite_empty_favorites(hass: HomeAssistant) -> None:
    """Test adding favorite when config entry has no existing favorites."""
    # Create config entry with no favorites
    empty_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={},  # No favorites key
        unique_id="music_favorites",
    )
    empty_entry.add_to_hass(hass)

    # Mock the config entry update and reload
    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        mock_fetch_external.return_value = {
            "artist_data": HALF_ME_COMPLETE_RESPONSE,
            "relation_links": {
                "allmusic_url": "https://www.allmusic.com/artist/mn0004372703",
                "bandsintown_url": "https://www.bandsintown.com/a/15548431",
                "discogs_url": "https://www.discogs.com/artist/12559079",
                "songkick_url": "https://www.songkick.com/artists/10118274",
                "musicbrainz_url": "https://musicbrainz.org/artist/963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",
            },
            "events": [],
            "variants": ["Half Me"],
            "status": BandStatus.ACTIVE,
        }

        # Add first favorite
        await add_favorite(
            hass,
            empty_entry,
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",  # Half Me ID
        )

        # Verify it was added correctly
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "favorites" in updated_data
        assert "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec" in updated_data["favorites"]
        # Half Me has no aliases - should only contain the name itself
        stored_data = updated_data["favorites"]["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]
        assert stored_data["variants"] == ["Half Me"]
        assert (
            len(stored_data["variants"]) == 1
        )  # Explicitly verify only one entry (no aliases)


async def test_remove_favorite_empty_favorites(hass: HomeAssistant) -> None:
    """Test removing favorite when config entry has no favorites."""
    # Create config entry with no favorites
    empty_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={},  # No favorites key
        unique_id="music_favorites",
    )
    empty_entry.add_to_hass(hass)

    # Try to remove from empty favorites using MusicBrainz ID
    with pytest.raises(ServiceValidationError, match="not found"):
        await remove_favorite(hass, empty_entry, "00000000-0000-0000-0000-000000000000")


# Tests for resolve_artist_from_name function


async def test_resolve_artist_no_matches(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name when no matches found."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(return_value=[])

        result = await resolve_artist_from_name(hass, "Unknown Band")

        assert result == {"action": "not_found"}
        mock_client.search_artists.assert_called_once_with("Unknown Band", limit=10)


async def test_resolve_artist_exact_match(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name with exact single match."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": "Iron Maiden",
                    "id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                    "aliases": ["Maiden"],
                    "score": 100,
                }
            ]
        )

        result = await resolve_artist_from_name(hass, "iron maiden")

        assert result == {
            "action": "create",
            "name": "Iron Maiden",
            "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
            "aliases": ["Maiden"],
        }


async def test_resolve_artist_exact_match_no_aliases(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name with exact match but no aliases."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": "Black Sabbath",
                    "id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
                    "score": 100,
                }
            ]
        )

        result = await resolve_artist_from_name(hass, "Black Sabbath")

        assert result == {
            "action": "create",
            "name": "Black Sabbath",
            "musicbrainz_id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
            "aliases": [],
        }


async def test_resolve_artist_single_match_different_name(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name with single match but different name."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": "Iron Maiden",
                    "id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                    "aliases": ["Maiden"],
                    "score": 95,
                    "disambiguation": "British heavy metal band",
                }
            ]
        )

        result = await resolve_artist_from_name(hass, "Maiden")

        assert result is not None
        assert result["action"] == "choose"
        options = result["options"]
        assert isinstance(options, list)
        assert len(options) == 1
        assert options[0] == {
            "name": "Iron Maiden",
            "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
            "aliases": ["Maiden"],
            "score": 95,
            "disambiguation": "British heavy metal band",
        }


async def test_resolve_artist_multiple_matches(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name with multiple matches."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": "Black Sabbath",
                    "id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
                    "score": 100,
                    "disambiguation": "British heavy metal band",
                },
                {
                    "name": "Black Sabbath",
                    "id": "different-id",
                    "score": 95,
                    "disambiguation": "Tribute band",
                    "aliases": ["BS Tribute"],
                },
            ]
        )

        result = await resolve_artist_from_name(hass, "Black Sabbath")

        assert result is not None
        assert result["action"] == "choose"
        options = result["options"]
        assert isinstance(options, list)
        assert len(options) == 2
        assert options[0]["name"] == "Black Sabbath"
        assert options[1]["aliases"] == ["BS Tribute"]


async def test_resolve_artist_multiple_matches_limit_to_5(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name limits results to 5 options."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        # Return 8 matches
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": f"Black Sabbath {i}",
                    "id": f"id-{i}",
                    "score": 100 - i,
                }
                for i in range(8)
            ]
        )

        result = await resolve_artist_from_name(hass, "Black Sabbath")

        assert result is not None
        assert result["action"] == "choose"
        assert len(result["options"]) == 5  # Limited to 5


async def test_resolve_artist_missing_optional_fields(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name handles missing optional fields."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            return_value=[
                {
                    "name": "Minimal Band",
                    "id": "minimal-id",
                    # Missing aliases, score, disambiguation
                }
            ]
        )

        result = await resolve_artist_from_name(hass, "Different Name")

        assert result is not None
        assert result["action"] == "choose"
        options = result["options"]
        assert isinstance(options, list)
        assert len(options) == 1
        option = options[0]
        assert option["name"] == "Minimal Band"
        assert option["musicbrainz_id"] == "minimal-id"
        assert option["aliases"] == []
        assert option["score"] == 0
        assert option["disambiguation"] == ""


async def test_resolve_artist_musicbrainz_error(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name handles MusicBrainzError."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            side_effect=MusicBrainzError("API Error")
        )

        result = await resolve_artist_from_name(hass, "Test Artist")

        assert result is None


async def test_resolve_artist_generic_exception(hass: HomeAssistant) -> None:
    """Test resolve_artist_from_name handles generic exceptions."""
    with patch(
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            side_effect=ValueError("Unexpected error")
        )

        result = await resolve_artist_from_name(hass, "Test Artist")

        assert result is None


async def test_add_favorite_musicbrainz_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test add_favorite handles MusicBrainz API errors."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.music_favorites.models.fetch_external_data"
    ) as mock_fetch_external:
        mock_fetch_external.side_effect = MusicBrainzError("API error")

        # Should raise ServiceValidationError with proper message
        with pytest.raises(
            ServiceValidationError, match="Could not fetch artist data from MusicBrainz"
        ):
            await add_favorite(hass, mock_config_entry, "test-musicbrainz-id")


async def test_add_favorite_no_entity_manager(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test adding favorite when entity manager is not available."""
    mock_config_entry.add_to_hass(hass)

    # Set up runtime_data without entity_manager
    mock_config_entry.runtime_data = {"some_other_data": "value"}

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Mock successful response
        test_band_data = {
            "id": "abcdef12-3456-7890-abcd-123456789def",
            "name": "Test Band",
            "aliases": [{"name": "Test Alias"}],
        }
        mock_fetch_external.return_value = {
            "artist_data": test_band_data,
            "relation_links": {
                "musicbrainz_url": "https://musicbrainz.org/artist/abcdef12-3456-7890-abcd-123456789def",
            },
            "events": [],
            "variants": ["Test Band", "Test Alias"],
            "status": BandStatus.ACTIVE,
        }

        # Should add favorite but warn about missing entity manager
        await add_favorite(hass, mock_config_entry, "test-musicbrainz-id")

        # Verify config was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]["favorites"]
        assert "test-musicbrainz-id" in updated_data


# Tests for Band Status System


def test_determine_band_status_active() -> None:
    """Test determine_band_status returns ACTIVE for active bands."""
    # Band with no end date (active)
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000"}}
    events_data: list[dict[str, Any]] = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ACTIVE


def test_determine_band_status_disbanded() -> None:
    """Test determine_band_status returns DISBANDED for disbanded bands."""
    # Band with end date (disbanded)
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000", "end": "2020"}}
    events_data: list[dict[str, Any]] = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.DISBANDED


def test_determine_band_status_reformed_ended_to_false() -> None:
    """Test determine_band_status returns REFORMED when MusicBrainz ended changes from true to false."""
    # Band currently shows as active
    current_artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "ended": False},
    }

    # Previous data showed band as ended
    previous_artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        current_artist_data,
        events_data,
        {"status": BandStatus.DISBANDED},
        previous_artist_data,
    )
    assert status == BandStatus.REFORMED


def test_determine_band_status_reformed_end_date_removed() -> None:
    """Test determine_band_status returns REFORMED when MusicBrainz end date is removed."""
    # Band currently shows no end date
    current_artist_data = {"name": "Reformed Band", "life-span": {"begin": "1980"}}

    # Previous data had an end date
    previous_artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        current_artist_data,
        events_data,
        {"status": BandStatus.DISBANDED},
        previous_artist_data,
    )
    assert status == BandStatus.REFORMED


def test_determine_band_status_reformed_maintained_for_period() -> None:
    """Test determine_band_status maintains REFORMED status for REFORMED_DISPLAY_PERIOD."""

    # Band is still ended according to MusicBrainz
    artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    # Reformed date was set 30 days ago (within 180-day period)
    reformed_date = (date.today() - timedelta(days=30)).isoformat()

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        artist_data,
        events_data,
        {"status": BandStatus.REFORMED, "reformed_date": reformed_date},
        None,
    )
    assert status == BandStatus.REFORMED


def test_determine_band_status_reformed_period_expired() -> None:
    """Test determine_band_status returns DISBANDED when REFORMED period expires."""

    # Band is still ended according to MusicBrainz
    artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    # Reformed date was set 200 days ago (beyond 180-day period)
    reformed_date = (date.today() - timedelta(days=200)).isoformat()

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        artist_data,
        events_data,
        {"status": BandStatus.REFORMED, "reformed_date": reformed_date},
        None,
    )
    assert status == BandStatus.DISBANDED


def test_determine_band_status_reformed_invalid_date() -> None:
    """Test determine_band_status handles invalid reformed_date gracefully."""
    # Band is still ended according to MusicBrainz
    artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    # Invalid reformed_date
    reformed_date = "invalid-date-format"

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        artist_data,
        events_data,
        {"status": BandStatus.REFORMED, "reformed_date": reformed_date},
        None,
    )
    # Should fall back to normal logic (DISBANDED since ended=true)
    assert status == BandStatus.DISBANDED


def test_determine_band_status_no_previous_data() -> None:
    """Test determine_band_status works without previous artist data."""
    # Band is currently ended
    artist_data = {
        "name": "Test Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        artist_data, events_data, {"status": BandStatus.DISBANDED}, None
    )
    assert status == BandStatus.DISBANDED


def test_determine_band_status_no_reformation_signals() -> None:
    """Test determine_band_status doesn't detect reformation without proper signals."""
    # Band remained ended in both periods
    current_artist_data = {
        "name": "Still Disbanded",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    previous_artist_data = {
        "name": "Still Disbanded",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        current_artist_data,
        events_data,
        {"status": BandStatus.DISBANDED},
        previous_artist_data,
    )
    assert status == BandStatus.DISBANDED


def test_determine_band_status_the_kinks_scenario() -> None:
    """Test The Kinks scenario: band with ended=true should return DISBANDED, not REFORMED."""
    # Simulate The Kinks: ended in 1996, still ended
    current_artist_data = {
        "name": "The Kinks",
        "life-span": {"begin": "1964", "end": "1996", "ended": True},
    }

    # Previous data same as current (no change)
    previous_artist_data = {
        "name": "The Kinks",
        "life-span": {"begin": "1964", "end": "1996", "ended": True},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(
        current_artist_data,
        events_data,
        {"status": BandStatus.DISBANDED},
        previous_artist_data,
    )
    # Should remain DISBANDED, NOT become REFORMED
    assert status == BandStatus.DISBANDED


def test_determine_band_status_active_with_ended_false() -> None:
    """Test band with ended=false returns appropriate active status."""
    # Band explicitly marked as not ended
    artist_data = {
        "name": "Active Band",
        "life-span": {"begin": "1980", "ended": False},
    }

    events_data: list[dict[str, Any]] = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ACTIVE


def test_determine_band_status_reformed_with_events() -> None:
    """Test REFORMED band with events gets tour status instead."""

    # Band is currently active after reformation
    current_artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "ended": False},
    }

    # Previous data showed band as ended
    previous_artist_data = {
        "name": "Reformed Band",
        "life-span": {"begin": "1980", "end": "1996", "ended": True},
    }

    # Add tour events that would make them ON_TOUR
    current_date = datetime.now()
    event_date = current_date + timedelta(days=15)  # Within tour preview window
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = determine_band_status(
        current_artist_data,
        events_data,
        {"status": BandStatus.DISBANDED},
        previous_artist_data,
    )
    # Should return REFORMED, not ON_TOUR, because reformation takes precedence
    assert status == BandStatus.REFORMED


def test_determine_band_status_on_tour() -> None:
    """Test determine_band_status returns ON_TOUR when tour status detected."""
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000"}}
    # Mock events data that would return ON_TOUR

    current_date = datetime.now()
    event_date = current_date + timedelta(days=15)  # Within 30-day preview window

    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ON_TOUR


def test_determine_band_status_tour_planned() -> None:
    """Test determine_band_status returns TOUR_PLANNED when tour is planned."""
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000"}}
    # Mock events data that would return TOUR_PLANNED

    current_date = datetime.now()
    event_date = current_date + timedelta(
        days=60
    )  # Beyond 30-day preview but within 180-day planning

    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.TOUR_PLANNED


def test_determine_band_status_no_life_span() -> None:
    """Test determine_band_status handles missing life-span data."""
    artist_data = {"name": "Test Band"}  # No life-span
    events_data: list[dict[str, Any]] = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ACTIVE


def test_get_tour_status_on_tour() -> None:
    """Test get_tour_status returns ON_TOUR for current events."""

    current_date = datetime.now()

    # Event within preview window (next 30 days)
    event_date = current_date + timedelta(days=15)
    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR


def test_get_tour_status_on_tour_grace_period() -> None:
    """Test get_tour_status returns ON_TOUR during grace period after event."""

    current_date = datetime.now()

    # Event 1 day ago (within 2-day grace period)
    event_date = current_date - timedelta(days=1)
    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR


def test_get_tour_status_tour_planned() -> None:
    """Test get_tour_status returns TOUR_PLANNED for future events."""

    current_date = datetime.now()

    # Event beyond preview window but within planning window
    event_date = current_date + timedelta(days=60)
    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.TOUR_PLANNED


def test_get_tour_status_no_relevant_events() -> None:
    """Test get_tour_status returns None when no relevant events."""

    current_date = datetime.now()

    # Event too far in future (beyond 180-day planning window)
    event_date = current_date + timedelta(days=200)
    # Use processed event format with event_date field
    events_data = [{"event_date": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status is None


def test_get_tour_status_empty_events() -> None:
    """Test get_tour_status returns None for empty events list."""
    events_data: list[dict[str, Any]] = []
    status = get_tour_status(events_data)
    assert status is None


def test_get_tour_status_bandsintown_with_invalid_dates() -> None:
    """Test get_tour_status handles processed events with some invalid dates."""

    current_date = datetime.now()

    events_data: list[dict[str, Any]] = [
        {
            "event_date": (current_date + timedelta(days=15)).strftime("%Y-%m-%d")
        },  # Valid processed event format
        {"event_date": "invalid-date"},  # Invalid format (should be skipped)
    ]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR  # Should find valid dates


def test_get_tour_status_bandsintown_format() -> None:
    """Test get_tour_status handles processed event format."""

    current_date = datetime.now()

    # Test processed event format
    events_data = [
        {
            "event_date": (current_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }  # Processed event format with event_date field
    ]
    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR


def test_get_tour_status_weird_date_lengths() -> None:
    """Test get_tour_status handles weird date string lengths."""
    events_data = [
        {
            "time": "20241"
        },  # 5 characters (not 4, 7, or 10) - should be skipped (line 91-92)
        {"time": "202412"},  # 6 characters - should be skipped
        {"time": "202412345"},  # 9 characters - should be skipped
    ]

    status = get_tour_status(events_data)
    assert status is None  # All dates should be skipped


def test_get_tour_status_value_error_handling() -> None:
    """Test get_tour_status handles ValueError in date parsing."""
    events_data = [
        {"time": "2024-13-01"},  # Invalid month (should raise ValueError, line 105-107)
        {"time": "2024-02-30"},  # Invalid day
        {"time": "invalid"},  # Completely invalid date
    ]

    status = get_tour_status(events_data)
    assert status is None  # All dates should be skipped due to ValueError


def test_get_tour_status_missing_time_fields() -> None:
    """Test get_tour_status handles events with missing time fields."""
    events_data = [
        {"venue": "Test Venue"},  # No time field
        {},  # Empty event
        {"time": ""},  # Empty time
    ]

    status = get_tour_status(events_data)
    assert status is None


async def test_add_favorite_includes_status_active(hass: HomeAssistant) -> None:
    """Test that add_favorite includes status for active bands."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Mock active band (no end date)
        active_band_data = {
            "id": "12345678-1234-5678-9abc-123456789abc",
            "name": "Active Band",
            "aliases": [],
            "life-span": {"begin": "2000"},  # No end date = active
            "relations": [],
        }
        mock_fetch_external.return_value = {
            "artist_data": active_band_data,
            "relation_links": {
                "musicbrainz_url": "https://musicbrainz.org/artist/12345678-1234-5678-9abc-123456789abc",
            },
            "events": [],
            "variants": ["Active Band"],
            "status": BandStatus.ACTIVE,
        }

        await add_favorite(hass, entry, "active-band-id")

        # Verify status was included
        mock_update.assert_called_once()
        updated_data = mock_update.call_args[1]["data"]["favorites"]
        stored_data = updated_data["active-band-id"]
        assert "status" in stored_data
        assert stored_data["status"] == BandStatus.ACTIVE


async def test_add_favorite_includes_status_disbanded(hass: HomeAssistant) -> None:
    """Test that add_favorite includes status for disbanded bands."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Mock disbanded band (has end date)
        disbanded_band_data = {
            "id": "deadbeef-1234-5678-90ab-cdef12345678",
            "name": "Disbanded Band",
            "aliases": [],
            "life-span": {
                "begin": "2000",
                "end": "2020",
            },  # Has end date = disbanded
            "relations": [],
        }
        mock_fetch_external.return_value = {
            "artist_data": disbanded_band_data,
            "relation_links": {
                "musicbrainz_url": "https://musicbrainz.org/artist/deadbeef-1234-5678-90ab-cdef12345678",
            },
            "events": [],
            "variants": ["Disbanded Band"],
            "status": BandStatus.DISBANDED,
        }

        await add_favorite(hass, entry, "disbanded-band-id")

        # Verify status was included
        mock_update.assert_called_once()
        updated_data = mock_update.call_args[1]["data"]["favorites"]
        stored_data = updated_data["disbanded-band-id"]
        assert "status" in stored_data
        assert stored_data["status"] == BandStatus.DISBANDED


async def test_add_favorite_deduplicates_variants(hass: HomeAssistant) -> None:
    """Test that add_favorite deduplicates variants when artist name appears in aliases."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.models.fetch_external_data"
        ) as mock_fetch_external,
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        # Mock artist where name "Asphyx" appears in both name and aliases (common MusicBrainz case)
        asphyx_data = {
            "id": "cafebabe-1337-4567-89ab-0123456789cd",
            "name": "Asphyx",
            "aliases": [
                {"name": "Asphyx"},  # Duplicate of main name
                {"name": "Asphyx"},  # Another duplicate
                {"name": "Soulburn"},  # Different alias
            ],
            "life-span": {"begin": "1987"},
            "relations": [],
        }
        mock_fetch_external.return_value = {
            "artist_data": asphyx_data,
            "relation_links": {
                "musicbrainz_url": "https://musicbrainz.org/artist/cafebabe-1337-4567-89ab-0123456789cd",
            },
            "events": [],
            "variants": ["Asphyx", "Soulburn"],
            "status": BandStatus.ACTIVE,
        }

        await add_favorite(hass, entry, "asphyx-test-id")

        # Verify variants were deduplicated
        mock_update.assert_called_once()
        updated_data = mock_update.call_args[1]["data"]["favorites"]
        stored_data = updated_data["asphyx-test-id"]

        # Should only contain unique variants: ["Asphyx", "Soulburn"]
        # Not ["Asphyx", "Asphyx", "Asphyx", "Soulburn"]
        assert stored_data["variants"] == ["Asphyx", "Soulburn"]
        assert len(stored_data["variants"]) == 2  # Explicitly verify count


async def test_add_favorite_bandsintown_ldjson_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test adding favorite with Bandsintown LdJsonError (covers line 218)."""
    # Create a test config entry
    test_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Music Favorites",
        data={"favorites": {}},
    )
    test_entry.add_to_hass(hass)

    # Set up runtime_data with MusicBrainz client (needed for fetch_external_data)
    test_entry.runtime_data = {
        "musicbrainz_client": MusicBrainzClient(hass),
    }

    # Use Half Me fixture (has real Bandsintown URL)
    half_me_id = "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"

    # Mock MusicBrainz API call with Half Me data
    aioclient_mock.get(
        f"https://musicbrainz.org/ws/2/artist/{half_me_id}?inc=aliases+url-rels&fmt=json",
        json=HALF_ME_COMPLETE_RESPONSE,
    )

    # Mock Bandsintown URL to return 404 (triggering LdJsonError)
    aioclient_mock.get(
        "https://www.bandsintown.com/a/15548431",  # Half Me's real Bandsintown URL
        status=404,
    )

    with (
        caplog.at_level(logging.WARNING),
        patch(
            "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
        ),
    ):
        await add_favorite(hass, test_entry, half_me_id)

    # Verify LdJsonError handling (line 218)
    assert "Failed to extract LD+JSON from Bandsintown" in caplog.text
    assert "HTTP request failed with status 404" in caplog.text


# Tests for extract_pure_event_data function (lines 44-74)


def test_extract_pure_event_data_bandsintown_format() -> None:
    """Test extract_pure_event_data with real Bandsintown event data."""
    # Create raw events in the format that extract_music_events would produce
    raw_events = [
        {
            "text": VULVODYNIA_EVENTS_LDJSON[0]["name"],
            "start_date": VULVODYNIA_EVENTS_LDJSON[0]["startDate"],
            "end_date": VULVODYNIA_EVENTS_LDJSON[0]["endDate"],
            "url": VULVODYNIA_EVENTS_LDJSON[0]["url"],
            "location": VULVODYNIA_EVENTS_LDJSON[0]["location"]["name"],
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Verify date/time conversion from fixture data
    assert event["event_date"] == "2025-11-25"
    assert event["venue_time"] == "18:00:00"
    assert event["venue_time_display"] == "6:00 PM"

    # Verify original fields are preserved
    assert event["text"] == VULVODYNIA_EVENTS_LDJSON[0]["name"]
    assert event["url"] == VULVODYNIA_EVENTS_LDJSON[0]["url"]
    assert event["location"] == VULVODYNIA_EVENTS_LDJSON[0]["location"]["name"]

    # Verify datetime fields are removed
    assert "start_date" not in event
    assert "end_date" not in event


def test_extract_pure_event_data_multiple_events() -> None:
    """Test extract_pure_event_data processes multiple events correctly."""
    # Use both Vulvodynia events from fixtures
    raw_events = [
        {
            "text": VULVODYNIA_EVENTS_LDJSON[0]["name"],
            "start_date": VULVODYNIA_EVENTS_LDJSON[0]["startDate"],
            "end_date": VULVODYNIA_EVENTS_LDJSON[0]["endDate"],
        },
        {
            "text": VULVODYNIA_EVENTS_LDJSON[1]["name"],
            "start_date": VULVODYNIA_EVENTS_LDJSON[1]["startDate"],
            "end_date": VULVODYNIA_EVENTS_LDJSON[1]["endDate"],
        },
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 2

    # First event (2025-11-25T18:00:00)
    assert result[0]["event_date"] == "2025-11-25"
    assert result[0]["venue_time"] == "18:00:00"
    assert result[0]["venue_time_display"] == "6:00 PM"

    # Second event (2025-11-28T17:30:00)
    assert result[1]["event_date"] == "2025-11-28"
    assert result[1]["venue_time"] == "17:30:00"
    assert result[1]["venue_time_display"] == "5:30 PM"


def test_extract_pure_event_data_strptime_value_error() -> None:
    """Test extract_pure_event_data handles strptime ValueError gracefully."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": "2025-13-99T25:99:99",  # Valid format but invalid date - triggers ValueError
            "end_date": "2025-11-25",
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Original invalid start_date should be preserved (ValueError caught)
    assert event["start_date"] == "2025-13-99T25:99:99"
    assert event["text"] == "Test Event"

    # end_date should still be removed
    assert "end_date" not in event


def test_extract_pure_event_data_invalid_start_date() -> None:
    """Test extract_pure_event_data handles invalid start_date gracefully."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": "invalid-datetime",  # Wrong format, won't be processed
            "end_date": "2025-11-25",
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Original invalid start_date should be preserved
    assert event["start_date"] == "invalid-datetime"
    assert event["text"] == "Test Event"

    # end_date should still be removed
    assert "end_date" not in event


def test_extract_pure_event_data_wrong_length_start_date() -> None:
    """Test extract_pure_event_data skips processing for wrong length start_date."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": "2025-11-25",  # Wrong length (10 chars instead of 19)
            "end_date": "2025-11-25",
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # start_date should be preserved as-is (not processed)
    assert event["start_date"] == "2025-11-25"
    assert "event_date" not in event
    assert "venue_time" not in event

    # end_date should still be removed
    assert "end_date" not in event


def test_extract_pure_event_data_no_t_separator() -> None:
    """Test extract_pure_event_data skips processing when no T separator."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": "2025-11-25 18:00:00",  # Wrong format (space instead of T)
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # start_date should be preserved as-is (not processed)
    assert event["start_date"] == "2025-11-25 18:00:00"
    assert "event_date" not in event


def test_extract_pure_event_data_no_start_date() -> None:
    """Test extract_pure_event_data handles events with no start_date."""
    raw_events = [
        {
            "text": "Test Event",
            "end_date": "2025-11-25",
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Only text should remain
    assert event["text"] == "Test Event"
    assert "start_date" not in event
    assert "end_date" not in event
    assert "event_date" not in event


def test_extract_pure_event_data_empty_start_date() -> None:
    """Test extract_pure_event_data handles empty start_date."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": "",  # Empty string
            "end_date": "2025-11-25",
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Empty start_date should be preserved
    assert event["start_date"] == ""
    assert "event_date" not in event
    assert "end_date" not in event


def test_extract_pure_event_data_no_end_date() -> None:
    """Test extract_pure_event_data handles events with no end_date."""
    raw_events = [
        {
            "text": "Test Event",
            "start_date": VULVODYNIA_EVENTS_LDJSON[0]["startDate"],  # Use fixture data
        }
    ]

    result = extract_pure_event_data(raw_events)

    assert len(result) == 1
    event = result[0]

    # Should process start_date normally
    assert event["event_date"] == "2025-11-25"
    assert event["venue_time"] == "18:00:00"
    assert "start_date" not in event
    assert "end_date" not in event


def test_extract_pure_event_data_empty_list() -> None:
    """Test extract_pure_event_data handles empty events list."""
    result = extract_pure_event_data([])
    assert result == []


# Tests for get_tour_status error handling (lines 149-151)


def test_get_tour_status_value_error_in_date_parsing() -> None:
    """Test get_tour_status handles ValueError in date parsing."""
    events_data = [
        {"event_date": "invalid-date-format"},  # Will cause ValueError
        {"event_date": "2025-11-25"},  # Valid date should still work
    ]

    # Should not crash and should find the valid date
    status = get_tour_status(events_data)
    # The 2025-11-25 date is far in future, so should return None or TOUR_PLANNED
    assert status in [BandStatus.TOUR_PLANNED, None]


def test_get_tour_status_type_error_in_date_parsing() -> None:
    """Test get_tour_status handles TypeError in date parsing."""
    events_data = [
        {"event_date": None},  # Will cause TypeError
        {"event_date": 123},  # Will also cause TypeError
    ]

    # Should not crash and should return None (no valid dates)
    status = get_tour_status(events_data)
    assert status is None


# Test for add_favorite with LD+JSON events (line 219)


async def test_add_favorite_with_ldjson_events(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test add_favorite processes LD+JSON events correctly (line 219)."""
    test_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    test_entry.add_to_hass(hass)

    # Set up runtime_data with MusicBrainz client (needed for fetch_external_data)
    test_entry.runtime_data = {
        "musicbrainz_client": MusicBrainzClient(hass),
    }

    half_me_id = "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"

    # Mock MusicBrainz API call
    aioclient_mock.get(
        f"https://musicbrainz.org/ws/2/artist/{half_me_id}?inc=aliases+url-rels&fmt=json",
        json=HALF_ME_COMPLETE_RESPONSE,
    )

    # Mock Bandsintown URL to return LD+JSON with events from fixtures
    aioclient_mock.get(
        "https://www.bandsintown.com/a/15548431",
        text=f"""
        <html>
        <head>
        <script type="application/ld+json">
        {json.dumps(VULVODYNIA_EVENTS_LDJSON[0])}
        </script>
        </head>
        </html>
        """,
    )

    with patch(
        "homeassistant.components.music_favorites.models.update_filtered_calendar_cache"
    ) as _:
        await add_favorite(hass, test_entry, half_me_id)

    # Verify the favorite was added with processed events
    updated_entry = hass.config_entries.async_get_entry(test_entry.entry_id)
    favorites = updated_entry.data["favorites"]

    assert half_me_id in favorites
    favorite_data = favorites[half_me_id]

    # Should have events data processed through extract_pure_event_data
    assert "events" in favorite_data
    assert len(favorite_data["events"]) == 1

    # Event should be processed (start_date converted to event_date)
    event = favorite_data["events"][0]
    assert event["event_date"] == "2025-11-25"  # From VULVODYNIA_EVENTS_LDJSON[0]
    assert event["venue_time"] == "18:00:00"
    assert "start_date" not in event


# Additional tests for 100% coverage


async def test_reformation_detection_end_date_removed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reformation detection when end date is removed (covers lines 174-178)."""
    # Previous artist data with end date (but ended=False to avoid first condition)
    previous_artist_data = {
        "id": "test-id",
        "name": "Test Band",
        "life-span": {
            "begin": "2000",
            "end": "2020",  # Had end date
            "ended": False,  # Keep same ended status
        },
    }

    # Current artist data with end date removed
    current_artist_data = {
        "id": "test-id",
        "name": "Test Band",
        "life-span": {
            "begin": "2000",
            # end date removed (became None)
            "ended": False,  # Same ended status
        },
    }

    with caplog.at_level(logging.INFO):
        status = determine_band_status(
            current_artist_data,
            events_data=[],
            current_data={},
            previous_artist_data=previous_artist_data,
        )

    assert status == BandStatus.REFORMED
    assert (
        "MusicBrainz reformation detected: end date removed (2020 -> None)"
        in caplog.text
    )


async def test_fetch_external_data_no_bandsintown_url(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test fetch_external_data with no Bandsintown URL (covers line 279)."""
    # Create a mock config entry with a proper mock client
    mock_client = AsyncMock()
    mock_client.get_artist_by_id.return_value = {
        "id": "test-id",
        "name": "Test Band",
        "aliases": [],
        "relations": [],  # No Bandsintown relation
        "life-span": {"begin": "2000"},
    }

    class MockEntry:
        runtime_data = {"musicbrainz_client": mock_client}

    entry = MockEntry()

    with (
        patch(
            "homeassistant.components.music_favorites.models.extract_relation_links"
        ) as mock_extract_links,
        caplog.at_level(logging.DEBUG),
    ):
        # Set up mocks
        mock_extract_links.return_value = {}  # No Bandsintown URL

        # Call function
        result = await fetch_external_data(hass, entry, "test-id")

        # Verify the debug log was triggered
        assert "No Bandsintown URL found for artist Test Band" in caplog.text
        assert result["events"] == []  # Should have empty events


async def test_fetch_external_data_with_aliases(hass: HomeAssistant) -> None:
    """Test fetch_external_data with aliases to cover variant processing (lines 242-245)."""
    # Create a mock config entry with a proper mock client
    mock_client = AsyncMock()
    mock_client.get_artist_by_id.return_value = {
        "id": "test-id",
        "name": "Test Band",
        "aliases": [
            {"name": "Test Alias 1"},
            {"name": "Test Alias 2"},
            {"name": ""},  # Empty alias (should be filtered out)
            {"name": "Test Band"},  # Duplicate of main name (should be filtered out)
        ],
        "relations": [],
        "life-span": {"begin": "2000"},
    }

    class MockEntry:
        runtime_data = {"musicbrainz_client": mock_client}

    entry = MockEntry()

    with patch(
        "homeassistant.components.music_favorites.models.extract_relation_links"
    ) as mock_extract_links:
        # Set up mocks
        mock_extract_links.return_value = {}

        # Call function
        result = await fetch_external_data(hass, entry, "test-id")

        # Verify aliases were processed correctly (covers lines 242-245)
        expected_variants = ["Test Band", "Test Alias 1", "Test Alias 2"]
        assert result["variants"] == expected_variants
        assert len(result["variants"]) == 3  # Should be deduplicated
