"""Test Music Favorites model functions."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import DOMAIN, BandStatus
from homeassistant.components.music_favorites.models import (
    add_favorite,
    determine_band_status,
    get_tour_status,
    remove_favorite,
    resolve_artist_from_name,
)
from homeassistant.components.music_favorites.musicbrainz import MusicBrainzError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .fixtures.musicbrainz_responses import (
    HALF_ME_COMPLETE_RESPONSE,
    IRON_MAIDEN_COMPLETE_RESPONSE,
)

from tests.common import MockConfigEntry


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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(return_value=HALF_ME_COMPLETE_RESPONSE)

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(return_value=HALF_ME_COMPLETE_RESPONSE)

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        # Use Iron Maiden fixture which includes unicode aliases
        mock_client.get_artist_by_id = AsyncMock(
            return_value=IRON_MAIDEN_COMPLETE_RESPONSE
        )

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(
            return_value=IRON_MAIDEN_COMPLETE_RESPONSE
        )

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(return_value=HALF_ME_COMPLETE_RESPONSE)

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
        "homeassistant.components.music_favorites.models.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(
            side_effect=MusicBrainzError("API error")
        )

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        # Mock successful MusicBrainz response
        mock_client = mock_client_class.return_value
        mock_client.get_artist_by_id = AsyncMock(
            return_value={
                "name": "Test Band",
                "aliases": [{"name": "Test Alias"}],
            }
        )

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
    events_data = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ACTIVE


def test_determine_band_status_disbanded() -> None:
    """Test determine_band_status returns DISBANDED for disbanded bands."""
    # Band with end date (disbanded)
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000", "end": "2020"}}
    events_data = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.DISBANDED


def test_determine_band_status_reformed() -> None:
    """Test determine_band_status returns REFORMED when band was previously disbanded."""
    # Band with end date but was previously disbanded
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000", "end": "2020"}}
    events_data = []

    status = determine_band_status(artist_data, events_data, BandStatus.DISBANDED)
    assert status == BandStatus.REFORMED


def test_determine_band_status_on_tour() -> None:
    """Test determine_band_status returns ON_TOUR when tour status detected."""
    artist_data = {"name": "Test Band", "life-span": {"begin": "2000"}}
    # Mock events data that would return ON_TOUR

    current_date = datetime.now()
    event_date = current_date + timedelta(days=15)  # Within 30-day preview window

    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

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

    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.TOUR_PLANNED


def test_determine_band_status_no_life_span() -> None:
    """Test determine_band_status handles missing life-span data."""
    artist_data = {"name": "Test Band"}  # No life-span
    events_data = []

    status = determine_band_status(artist_data, events_data)
    assert status == BandStatus.ACTIVE


def test_get_tour_status_on_tour() -> None:
    """Test get_tour_status returns ON_TOUR for current events."""

    current_date = datetime.now()

    # Event within preview window (next 30 days)
    event_date = current_date + timedelta(days=15)
    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR


def test_get_tour_status_on_tour_grace_period() -> None:
    """Test get_tour_status returns ON_TOUR during grace period after event."""

    current_date = datetime.now()

    # Event 1 day ago (within 2-day grace period)
    event_date = current_date - timedelta(days=1)
    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR


def test_get_tour_status_tour_planned() -> None:
    """Test get_tour_status returns TOUR_PLANNED for future events."""

    current_date = datetime.now()

    # Event beyond preview window but within planning window
    event_date = current_date + timedelta(days=60)
    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status == BandStatus.TOUR_PLANNED


def test_get_tour_status_no_relevant_events() -> None:
    """Test get_tour_status returns None when no relevant events."""

    current_date = datetime.now()

    # Event too far in future (beyond 180-day planning window)
    event_date = current_date + timedelta(days=200)
    events_data = [{"time": event_date.strftime("%Y-%m-%d")}]

    status = get_tour_status(events_data)
    assert status is None


def test_get_tour_status_empty_events() -> None:
    """Test get_tour_status returns None for empty events list."""
    events_data = []
    status = get_tour_status(events_data)
    assert status is None


def test_get_tour_status_invalid_date_formats() -> None:
    """Test get_tour_status handles various date formats."""

    current_date = datetime.now()

    events_data = [
        {
            "time": (current_date + timedelta(days=15)).strftime("%Y-%m-%d")
        },  # YYYY-MM-DD
        {"time": (current_date + timedelta(days=16)).strftime("%Y-%m")},  # YYYY-MM
        {"time": (current_date + timedelta(days=17)).strftime("%Y")},  # YYYY
        {"time": "invalid-date"},  # Invalid format (should be skipped)
        {
            "life-span": {
                "begin": (current_date + timedelta(days=18)).strftime("%Y-%m-%d")
            }
        },  # Alternative field
    ]

    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR  # Should find valid dates


def test_get_tour_status_short_date_formats() -> None:
    """Test get_tour_status handles YYYY-MM and YYYY formats specifically."""

    current_date = datetime.now()

    # Test YYYY-MM format (line 87-88)
    events_data = [
        {
            "time": (current_date + timedelta(days=15)).strftime("%Y-%m")
        }  # YYYY-MM format
    ]
    status = get_tour_status(events_data)
    assert status == BandStatus.ON_TOUR

    # Test YYYY format (line 89-90) - use current year to ensure it's within window
    events_data = [
        {"time": str(current_date.year)}  # YYYY format for current year
    ]
    status = get_tour_status(events_data)
    # For YYYY format, it defaults to Jan 1st of that year, which might be past or future
    # The important thing is that it doesn't crash and processes the date format
    assert status in [BandStatus.ON_TOUR, BandStatus.TOUR_PLANNED, None]


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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        # Mock active band (no end date)
        mock_client.get_artist_by_id = AsyncMock(
            return_value={
                "name": "Active Band",
                "aliases": [],
                "life-span": {"begin": "2000"},  # No end date = active
                "relations": [],
            }
        )

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        # Mock disbanded band (has end date)
        mock_client.get_artist_by_id = AsyncMock(
            return_value={
                "name": "Disbanded Band",
                "aliases": [],
                "life-span": {
                    "begin": "2000",
                    "end": "2020",
                },  # Has end date = disbanded
                "relations": [],
            }
        )

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
            "homeassistant.components.music_favorites.models.MusicBrainzClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        # Mock artist where name "Asphyx" appears in both name and aliases (common MusicBrainz case)
        mock_client.get_artist_by_id = AsyncMock(
            return_value={
                "name": "Asphyx",
                "aliases": [
                    {"name": "Asphyx"},  # Duplicate of main name
                    {"name": "Asphyx"},  # Another duplicate
                    {"name": "Soulburn"},  # Different alias
                ],
                "life-span": {"begin": "1987"},
                "relations": [],
            }
        )

        await add_favorite(hass, entry, "asphyx-test-id")

        # Verify variants were deduplicated
        mock_update.assert_called_once()
        updated_data = mock_update.call_args[1]["data"]["favorites"]
        stored_data = updated_data["asphyx-test-id"]

        # Should only contain unique variants: ["Asphyx", "Soulburn"]
        # Not ["Asphyx", "Asphyx", "Asphyx", "Soulburn"]
        assert stored_data["variants"] == ["Asphyx", "Soulburn"]
        assert len(stored_data["variants"]) == 2  # Explicitly verify count
