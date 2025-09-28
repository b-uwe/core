"""Test the Music Favorites sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.musicbrainz import extract_relation_links
from homeassistant.components.music_favorites.sensor import (
    EntityManager,
    FavoriteSensor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .conftest import mock_musicbrainz_client  # noqa: F401
from .fixtures.musicbrainz_responses import (
    HALF_ME_COMPLETE_RESPONSE,
    IRON_MAIDEN_COMPLETE_RESPONSE,
)


@pytest.fixture
def mock_config_entry_with_iron_maiden():
    """Mock config entry with Iron Maiden fixture data."""
    # Extract relation links from fixture
    relation_links = extract_relation_links(IRON_MAIDEN_COMPLETE_RESPONSE)

    # Extract name and aliases from fixture
    name = IRON_MAIDEN_COMPLETE_RESPONSE["name"]
    aliases = [
        alias.get("name", "")
        for alias in IRON_MAIDEN_COMPLETE_RESPONSE.get("aliases", [])
        if alias.get("name")
    ]
    variants = [name, *aliases]

    favorites_data = {
        IRON_MAIDEN_COMPLETE_RESPONSE["id"]: {
            "variants": variants,
            **relation_links,
        }
    }

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {"favorites": favorites_data}
    mock_entry.runtime_data = {}
    return mock_entry


@pytest.fixture
def mock_config_entry_with_half_me():
    """Mock config entry with Half Me fixture data."""
    # Extract relation links from fixture
    relation_links = extract_relation_links(HALF_ME_COMPLETE_RESPONSE)

    # Extract name and aliases from fixture
    name = HALF_ME_COMPLETE_RESPONSE["name"]
    aliases = [
        alias.get("name", "")
        for alias in HALF_ME_COMPLETE_RESPONSE.get("aliases", [])
        if alias.get("name")
    ]
    variants = [name, *aliases]

    favorites_data = {
        HALF_ME_COMPLETE_RESPONSE["id"]: {
            "variants": variants,
            **relation_links,
        }
    }

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {"favorites": favorites_data}
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
def entity_manager(
    hass: HomeAssistant, mock_config_entry_with_iron_maiden, mock_device_info
):
    """Create an EntityManager for testing."""
    mock_add_entities = MagicMock()
    device_info = DeviceInfo(**mock_device_info)
    return EntityManager(
        hass, mock_config_entry_with_iron_maiden, mock_add_entities, device_info
    )


class TestEntityManager:
    """Test the EntityManager class."""

    async def test_init(self, entity_manager, mock_config_entry_with_iron_maiden):
        """Test EntityManager initialization."""
        assert entity_manager.hass is not None
        assert entity_manager.entry == mock_config_entry_with_iron_maiden
        assert entity_manager._async_add_entities is not None
        assert entity_manager._device_info is not None

    async def test_add_favorite_entity_new(self, entity_manager):
        """Test adding a new favorite entity."""
        # Use a new MusicBrainz ID that's not in the fixture
        musicbrainz_id = "5b11f4ce-a62d-471e-81fc-a69a8278c7da"  # Black Sabbath
        favorite_data = {"variants": ["Black Sabbath"]}

        # Call the method
        entity_manager.add_favorite_entity(musicbrainz_id, favorite_data)

        # Verify entity was created and added
        entity_manager._async_add_entities.assert_called_once()

        # Verify the entity was created correctly
        call_args = entity_manager._async_add_entities.call_args[0][0]
        assert len(call_args) == 1
        entity = call_args[0]
        assert isinstance(entity, FavoriteSensor)
        assert entity._favorite_key == musicbrainz_id
        assert entity._favorite_variants == ["Black Sabbath"]

    async def test_add_favorite_entity_duplicate(self, entity_manager):
        """Test adding a duplicate entity (already in entity registry)."""
        musicbrainz_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]  # Iron Maiden from fixture
        favorite_data = {"variants": ["Iron Maiden"]}

        # Mock entity registry to return existing entity
        with patch(
            "homeassistant.helpers.entity_registry.async_get"
        ) as mock_get_registry:
            mock_registry = mock_get_registry.return_value
            mock_registry.async_get_entity_id.return_value = (
                "sensor.music_favorites_iron_maiden"
            )

            # Try to add entity that already exists in registry
            entity_manager.add_favorite_entity(musicbrainz_id, favorite_data)

            # Verify it wasn't added (already exists in registry)
            entity_manager._async_add_entities.assert_not_called()


class TestFavoriteSensor:
    """Test the FavoriteSensor class."""

    @pytest.fixture
    def favorite_sensor(self, mock_device_info, mock_config_entry_with_iron_maiden):
        """Create a FavoriteSensor for testing using Iron Maiden fixture data."""
        # Use Iron Maiden data from the fixture
        favorites_data = mock_config_entry_with_iron_maiden.data["favorites"]
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        favorite_data = favorites_data[iron_maiden_id]

        return FavoriteSensor(
            iron_maiden_id,
            favorite_data,
            mock_device_info,
        )

    async def test_init(self, favorite_sensor):
        """Test FavoriteSensor initialization."""
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert favorite_sensor._favorite_key == iron_maiden_id
        assert favorite_sensor._favorite_variants[0] == "Iron Maiden"  # First variant
        assert favorite_sensor._attr_name == "Iron Maiden"
        assert favorite_sensor._attr_unique_id == f"favorite_{iron_maiden_id}"
        assert favorite_sensor._attr_icon == "mdi:guitar-electric"
        assert hasattr(favorite_sensor, "_attr_has_entity_name")

    async def test_extra_state_attributes(self, favorite_sensor):
        """Test extra state attributes."""
        attributes = favorite_sensor.extra_state_attributes
        assert attributes is not None
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert attributes["musicbrainz_id"] == iron_maiden_id
        # Should have all Iron Maiden variants except first one (display name)
        expected_variants = favorite_sensor._favorite_variants[1:]
        assert attributes["variants"] == expected_variants

        # Should include relation URLs
        assert "allmusic_url" in attributes
        assert "bandsintown_url" in attributes
        assert "discogs_url" in attributes
        assert "songkick_url" in attributes

    async def test_native_value(self, favorite_sensor):
        """Test native value property."""
        # Currently returns None - could be extended for future features
        assert favorite_sensor.native_value is None

    async def test_entity_id_generation(self, mock_device_info):
        """Test entity ID generation with various artist names."""
        # Test with special characters
        favorite_data = {"variants": ["Motörhead & Friends!"]}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
        )
        # Should create safe entity ID with "act_" prefix
        assert sensor.entity_id == "sensor.music_favorites_act_motörhead_friends"

        # Test with multiple spaces and hyphens
        favorite_data2 = {"variants": ["Iron  Maiden - Legacy"]}
        sensor2 = FavoriteSensor(
            "test-id-2",
            favorite_data2,
            mock_device_info,
        )
        assert sensor2.entity_id == "sensor.music_favorites_act_iron_maiden_legacy"


class TestFavoriteSensorWithRelationLinks:
    """Test the FavoriteSensor class with relation links from fixtures."""

    async def test_iron_maiden_sensor_with_relation_links(self, mock_device_info):
        """Test FavoriteSensor with Iron Maiden fixture data including relation links."""
        # Extract data from fixture like the real code does
        relation_links = extract_relation_links(IRON_MAIDEN_COMPLETE_RESPONSE)

        # Extract name and aliases from fixture
        name = IRON_MAIDEN_COMPLETE_RESPONSE["name"]
        aliases = [
            alias.get("name", "")
            for alias in IRON_MAIDEN_COMPLETE_RESPONSE.get("aliases", [])
            if alias.get("name")
        ]
        variants = [name, *aliases]

        # Create favorite data structure
        favorite_data = {
            "variants": variants,
            **relation_links,
        }

        # Create sensor with complete favorite data
        sensor = FavoriteSensor(
            IRON_MAIDEN_COMPLETE_RESPONSE["id"],
            favorite_data,
            mock_device_info,
        )

        # Test basic properties
        assert sensor._favorite_key == IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert sensor._favorite_variants == variants
        assert sensor._attr_name == "Iron Maiden"  # First variant
        assert (
            sensor._attr_unique_id == f"favorite_{IRON_MAIDEN_COMPLETE_RESPONSE['id']}"
        )

        # Test extra state attributes include relation links
        attributes = sensor.extra_state_attributes
        assert attributes is not None

        # Check basic attributes
        assert attributes["musicbrainz_id"] == IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert attributes["variants"] == variants[1:]  # All except display name

        # Check relation links are included as individual attributes
        assert "allmusic_url" in attributes
        assert (
            attributes["allmusic_url"] == "https://www.allmusic.com/artist/mn0000098465"
        )
        assert "bandsintown_url" in attributes
        assert attributes["bandsintown_url"] == "https://www.bandsintown.com/a/1301"
        assert "discogs_url" in attributes
        assert attributes["discogs_url"] == "https://www.discogs.com/artist/251595"
        assert "songkick_url" in attributes
        assert attributes["songkick_url"] == "https://www.songkick.com/artists/438390"

        # Ensure name attributes are NOT included (only URLs)
        assert "allmusic_name" not in attributes
        assert "bandsintown_name" not in attributes
        assert "discogs_name" not in attributes
        assert "songkick_name" not in attributes

    async def test_half_me_sensor_with_relation_links(self, mock_device_info):
        """Test FavoriteSensor with Half Me fixture data including relation links."""
        # Extract data from fixture like the real code does
        relation_links = extract_relation_links(HALF_ME_COMPLETE_RESPONSE)

        # Extract name and aliases from fixture
        name = HALF_ME_COMPLETE_RESPONSE["name"]
        aliases = [
            alias.get("name", "")
            for alias in HALF_ME_COMPLETE_RESPONSE.get("aliases", [])
            if alias.get("name")
        ]
        variants = [name, *aliases]  # Half Me has no aliases, so just ["Half Me"]

        # Create favorite data structure
        favorite_data = {
            "variants": variants,
            **relation_links,
        }

        # Create sensor with complete favorite data
        sensor = FavoriteSensor(
            HALF_ME_COMPLETE_RESPONSE["id"],
            favorite_data,
            mock_device_info,
        )

        # Test basic properties
        assert sensor._favorite_key == HALF_ME_COMPLETE_RESPONSE["id"]
        assert sensor._favorite_variants == variants
        assert sensor._attr_name == "Half Me"  # First variant

        # Test extra state attributes include relation links
        attributes = sensor.extra_state_attributes
        assert attributes is not None

        # Check basic attributes
        assert attributes["musicbrainz_id"] == HALF_ME_COMPLETE_RESPONSE["id"]
        assert (
            attributes["variants"] == variants[1:]
        )  # Should be empty for Half Me (no aliases)

        # Check relation links are included as individual attributes
        assert "allmusic_url" in attributes
        assert (
            attributes["allmusic_url"] == "https://www.allmusic.com/artist/mn0004372703"
        )
        assert "bandsintown_url" in attributes
        assert attributes["bandsintown_url"] == "https://www.bandsintown.com/a/15548431"
        assert "discogs_url" in attributes
        assert attributes["discogs_url"] == "https://www.discogs.com/artist/12559079"
        assert "songkick_url" in attributes
        assert attributes["songkick_url"] == "https://www.songkick.com/artists/10118274"

    async def test_sensor_without_relation_links(self, mock_device_info):
        """Test FavoriteSensor with favorite data that has no relation links."""
        # Create favorite data without relation links
        favorite_data = {
            "variants": ["Test Artist", "Test Alias"],
        }

        sensor = FavoriteSensor(
            "test-musicbrainz-id",
            favorite_data,
            mock_device_info,
        )

        # Test extra state attributes
        attributes = sensor.extra_state_attributes
        assert attributes is not None

        # Check basic attributes
        assert attributes["musicbrainz_id"] == "test-musicbrainz-id"
        assert attributes["variants"] == ["Test Alias"]  # All except display name

        # Should not have any relation link attributes
        for key in attributes:
            assert not key.endswith("_url"), f"Unexpected URL attribute: {key}"

    async def test_sensor_partial_relation_links(self, mock_device_info):
        """Test FavoriteSensor with favorite data that has only some relation links."""
        # Create favorite data with only some relation links
        favorite_data = {
            "variants": ["Test Artist"],
            "allmusic_url": "https://www.allmusic.com/artist/test",
            "allmusic_name": "AllMusic",
            "discogs_url": "https://www.discogs.com/artist/test",
            "discogs_name": "Discogs",
            # Missing bandsintown and songkick
        }

        sensor = FavoriteSensor(
            "test-musicbrainz-id",
            favorite_data,
            mock_device_info,
        )

        # Test extra state attributes
        attributes = sensor.extra_state_attributes
        assert attributes is not None

        # Check basic attributes
        assert attributes["musicbrainz_id"] == "test-musicbrainz-id"
        assert attributes["variants"] == []  # No aliases

        # Should have only the URL attributes that were provided
        assert "allmusic_url" in attributes
        assert attributes["allmusic_url"] == "https://www.allmusic.com/artist/test"
        assert "discogs_url" in attributes
        assert attributes["discogs_url"] == "https://www.discogs.com/artist/test"

        # Should not have bandsintown or songkick
        assert "bandsintown_url" not in attributes
        assert "songkick_url" not in attributes

        # Should not have name attributes (only URLs)
        assert "allmusic_name" not in attributes
        assert "discogs_name" not in attributes
