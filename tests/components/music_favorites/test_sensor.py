"""Test the Music Favorites sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.music_favorites.sensor import (
    EntityManager,
    FavoriteSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .conftest import mock_musicbrainz_client  # noqa: F401

# Test data
TEST_FAVORITES = {
    "ca891d65-d9b0-4258-89f7-e6ba29d83767": ["Iron Maiden", "Ironmaiden"],
    "f0d05c64-9959-4ae1-899b-acf51b97638c": ["Dyscarnate"],
}


@pytest.fixture
def mock_config_entry():
    """Mock config entry with favorites data."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {"favorites": TEST_FAVORITES}
    mock_entry.runtime_data = {}
    return mock_entry


@pytest.fixture
def mock_device_info():
    """Mock device info for testing."""
    return DeviceInfo(
        identifiers={("music_favorites", "test_device")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
    )


@pytest.fixture
def entity_manager(hass: HomeAssistant, mock_config_entry, mock_device_info):
    """Create an EntityManager for testing."""
    mock_add_entities = MagicMock()
    return EntityManager(hass, mock_config_entry, mock_add_entities)


class TestEntityManager:
    """Test the EntityManager class."""

    async def test_init(self, entity_manager, mock_config_entry):
        """Test EntityManager initialization."""
        assert entity_manager.hass is not None
        assert entity_manager.entry == mock_config_entry
        assert entity_manager._async_add_entities is not None
        assert entity_manager._added_entities == set()
        assert entity_manager._bands_device_info is not None

    async def test_add_favorite_entity_new(self, entity_manager):
        """Test adding a new favorite entity."""
        # Test data
        musicbrainz_id = "test-id-123"
        favorite_variants = ["Test Artist", "Test Alias"]

        # Call the method
        entity_manager.add_favorite_entity(musicbrainz_id, favorite_variants)

        # Verify entity was added
        assert musicbrainz_id in entity_manager._added_entities
        entity_manager._async_add_entities.assert_called_once()

        # Verify the entity was created correctly
        call_args = entity_manager._async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        entity = call_args[0]
        assert isinstance(entity, FavoriteSensor)
        assert entity._favorite_key == musicbrainz_id
        assert entity._favorite_variants == favorite_variants

    async def test_add_favorite_entity_duplicate(self, entity_manager):
        """Test adding a duplicate favorite entity (should be ignored)."""
        # Test data
        musicbrainz_id = "test-id-123"
        favorite_variants = ["Test Artist"]

        # Add entity first time
        entity_manager.add_favorite_entity(musicbrainz_id, favorite_variants)
        assert entity_manager._async_add_entities.call_count == 1

        # Try to add the same entity again
        entity_manager.add_favorite_entity(musicbrainz_id, favorite_variants)

        # Verify it wasn't added again
        assert entity_manager._async_add_entities.call_count == 1
        assert musicbrainz_id in entity_manager._added_entities

    async def test_sync_entities_with_config(self, entity_manager):
        """Test syncing entities with config entry data."""
        # Initial sync should add all favorites from config
        entity_manager.sync_entities_with_config()

        # Verify all favorites were added
        assert entity_manager._async_add_entities.call_count == 1
        call_args = entity_manager._async_add_entities.call_args[0][0]
        assert len(call_args) == 2  # Two favorites in TEST_FAVORITES

        # Verify entities were tracked
        assert "ca891d65-d9b0-4258-89f7-e6ba29d83767" in entity_manager._added_entities
        assert "f0d05c64-9959-4ae1-899b-acf51b97638c" in entity_manager._added_entities

    async def test_sync_entities_with_config_no_new_entities(self, entity_manager):
        """Test syncing when all entities are already added."""
        # Add entities first
        entity_manager.sync_entities_with_config()
        assert entity_manager._async_add_entities.call_count == 1

        # Sync again - should not add any new entities
        entity_manager.sync_entities_with_config()
        assert entity_manager._async_add_entities.call_count == 1

    async def test_sync_entities_with_config_empty_favorites(self, entity_manager):
        """Test syncing with empty favorites."""
        # Clear favorites in config
        entity_manager.entry.data = {"favorites": {}}

        # Sync should not add any entities
        entity_manager.sync_entities_with_config()
        entity_manager._async_add_entities.assert_not_called()


class TestFavoriteSensor:
    """Test the FavoriteSensor class."""

    @pytest.fixture
    def favorite_sensor(self, mock_device_info):
        """Create a FavoriteSensor for testing."""
        return FavoriteSensor(
            "test-musicbrainz-id",
            ["Test Artist", "Test Alias"],
            mock_device_info,
        )

    async def test_init(self, favorite_sensor):
        """Test FavoriteSensor initialization."""
        assert favorite_sensor._favorite_key == "test-musicbrainz-id"
        assert favorite_sensor._favorite_variants == ["Test Artist", "Test Alias"]
        assert favorite_sensor._attr_name == "Test Artist"
        assert favorite_sensor._attr_unique_id == "favorite_test-musicbrainz-id"
        assert favorite_sensor._attr_translation_key == "favorite_act"
        assert favorite_sensor._attr_icon == "mdi:guitar-electric"
        assert favorite_sensor._attr_has_entity_name is True

    async def test_extra_state_attributes(self, favorite_sensor):
        """Test extra state attributes."""
        attributes = favorite_sensor.extra_state_attributes
        assert attributes is not None
        assert attributes["musicbrainz_id"] == "test-musicbrainz-id"
        assert attributes["variants"] == ["Test Alias"]  # All except display name

    async def test_native_value(self, favorite_sensor):
        """Test native value property."""
        # Currently returns None - could be extended for future features
        assert favorite_sensor.native_value is None

    async def test_entity_id_generation(self, mock_device_info):
        """Test entity ID generation with various artist names."""
        # Test with special characters
        sensor = FavoriteSensor(
            "test-id",
            ["Motörhead & Friends!"],
            mock_device_info,
        )
        # Should create safe entity ID
        assert sensor._attr_entity_id == "sensor.music_favorites_motörhead_friends"

        # Test with multiple spaces and hyphens
        sensor2 = FavoriteSensor(
            "test-id-2",
            ["Iron  Maiden - Legacy"],
            mock_device_info,
        )
        assert sensor2._attr_entity_id == "sensor.music_favorites_iron_maiden_legacy"
