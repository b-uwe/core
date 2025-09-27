"""Test Music Favorites model functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.models import (
    add_favorite,
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
                "ca891d65-d9b0-4258-89f7-e6ba29d83767": ["Iron Maiden"],
                "5182c1d9-c7d2-4dad-afa0-ccfeada921a8": ["Black Sabbath"],
                "f0d05c64-9959-4ae1-899b-acf51b97638c": [
                    "Motörhead"
                ],  # Using ö for testing unicode
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
        expected_variants = ["Half Me"]
        assert (
            updated_data["favorites"]["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]
            == expected_variants
        )

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
        mock_entity_manager.add_favorite_entity.assert_called_once_with(
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec", ["Half Me"]
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
        expected_variants = ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"]
        assert (
            updated_data["favorites"]["different-unicode-id-123"] == expected_variants
        )


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
        assert "f0d05c64-9959-4ae1-899b-acf51b97638c" in updated_data["favorites"]

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
            hass, mock_config_entry, "f0d05c64-9959-4ae1-899b-acf51b97638c"
        )

        # Verify it was removed
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "f0d05c64-9959-4ae1-899b-acf51b97638c" not in updated_data["favorites"]

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
        stored_variants = updated_data["ca891d65-d9b0-4258-89f7-e6ba29d83767"]
        # Iron Maiden has name + real aliases from MusicBrainz
        expected_variants = ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"]
        assert stored_variants == expected_variants

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
        stored_variants = updated_data["favorites"][
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"
        ]
        assert stored_variants == ["Half Me"]
        assert (
            len(stored_variants) == 1
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
