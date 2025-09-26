"""Test Music Favorites model functions."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.models import (
    add_favorite,
    remove_favorite,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

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

    # Mock the config entry update and reload
    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        # Add a new favorite
        await add_favorite(
            hass,
            mock_config_entry,
            "Led Zeppelin",
            "678d88b2-87b0-403b-b63d-5da7465aecc3",
        )

        # Verify the config entry was updated with new favorite
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_entry = call_args[0][0]  # First argument (the entry)
        updated_data = call_args[1]["data"]  # The data keyword argument

        assert updated_entry == mock_config_entry
        assert "678d88b2-87b0-403b-b63d-5da7465aecc3" in updated_data["favorites"]
        assert updated_data["favorites"]["678d88b2-87b0-403b-b63d-5da7465aecc3"] == [
            "Led Zeppelin"
        ]

        # Verify the config entry was reloaded (to create new entities)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


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
            "Iron Maiden",
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",
        )


async def test_add_favorite_case_insensitive_duplicate(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test that duplicate detection works regardless of case/spacing."""
    mock_config_entry.add_to_hass(hass)

    # Try to add "IRON MAIDEN" when "Iron Maiden" already exists
    # This should fail because the MusicBrainz ID already exists
    with pytest.raises(ServiceValidationError, match="already exists"):
        await add_favorite(
            hass,
            mock_config_entry,
            "IRON MAIDEN",
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",
        )


async def test_add_favorite_unicode_handling(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test adding favorites with unicode characters."""
    mock_config_entry.add_to_hass(hass)

    # Mock the config entry update and reload
    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch.object(hass.config_entries, "async_reload"),
    ):
        # Add a favorite with unicode characters
        await add_favorite(
            hass, mock_config_entry, "Sigur Rós", "703d7b12-18a8-4acb-8d8e-7badf2f3bd5c"
        )

        # Verify it was added correctly
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        # The ID should be the MusicBrainz ID
        assert "703d7b12-18a8-4acb-8d8e-7badf2f3bd5c" in updated_data["favorites"]
        assert updated_data["favorites"]["703d7b12-18a8-4acb-8d8e-7badf2f3bd5c"] == [
            "Sigur Rós"
        ]


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
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        # Remove an existing favorite
        await remove_favorite(hass, mock_config_entry, "Iron Maiden")

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
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


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
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        # Remove using different case
        await remove_favorite(hass, mock_config_entry, "IRON MAIDEN")

        # Verify it was still found and removed
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "ca891d65-d9b0-4258-89f7-e6ba29d83767" not in updated_data["favorites"]

        # Verify the config entry was reloaded (to update UI)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


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
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        # Remove the unicode favorite
        await remove_favorite(hass, mock_config_entry, "Motörhead")

        # Verify it was removed
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "f0d05c64-9959-4ae1-899b-acf51b97638c" not in updated_data["favorites"]

        # Verify the config entry was reloaded (to update UI)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_remove_favorite_not_found(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test removing a non-existent favorite raises an error."""
    mock_config_entry.add_to_hass(hass)

    # Try to remove a favorite that doesn't exist
    with pytest.raises(ServiceValidationError, match="not found"):
        await remove_favorite(hass, mock_config_entry, "Non-existent Band")


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
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        # Remove should still succeed even if entity isn't in registry
        await remove_favorite(hass, mock_config_entry, "Iron Maiden")

        # Verify the favorite was still removed from config
        mock_update.assert_called_once()

        # Verify registry cleanup was attempted but remove was NOT called (because entity_id was None)
        mock_entity_registry.async_get_entity_id.assert_called_once()
        mock_entity_registry.async_remove.assert_not_called()

        # Verify the config entry was reloaded (to update UI)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


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
        patch.object(hass.config_entries, "async_reload"),
    ):
        # Add first favorite
        await add_favorite(
            hass, empty_entry, "The Kinks", "17b53d9f-5db6-4f6a-808a-0769e99b5111"
        )

        # Verify it was added correctly
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert "favorites" in updated_data
        assert "17b53d9f-5db6-4f6a-808a-0769e99b5111" in updated_data["favorites"]
        assert updated_data["favorites"]["17b53d9f-5db6-4f6a-808a-0769e99b5111"] == [
            "The Kinks"
        ]


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

    # Try to remove from empty favorites
    with pytest.raises(ServiceValidationError, match="not found"):
        await remove_favorite(hass, empty_entry, "Any Band")
