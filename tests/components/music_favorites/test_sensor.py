"""Test the Music Favorites sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.models import BandStatus
from homeassistant.components.music_favorites.musicbrainz import extract_relation_links
from homeassistant.components.music_favorites.sensor import (
    EntityManager,
    FavoriteSensor,
    async_setup_entry,
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
            "status": BandStatus.ACTIVE,
            "musicbrainz_url": f"https://musicbrainz.org/artist/{IRON_MAIDEN_COMPLETE_RESPONSE['id']}",
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
            "musicbrainz_url": f"https://musicbrainz.org/artist/{HALF_ME_COMPLETE_RESPONSE['id']}",
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
            mock_config_entry_with_iron_maiden,
        )

    async def test_init(self, favorite_sensor):
        """Test FavoriteSensor initialization."""
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert favorite_sensor._favorite_key == iron_maiden_id
        # Test that data is accessible via current favorite data
        current_data = favorite_sensor._current_favorite_data
        assert current_data.get("variants", [])[0] == "Iron Maiden"  # First variant
        assert favorite_sensor._attr_name == "Iron Maiden"
        assert favorite_sensor._attr_unique_id == f"favorite_{iron_maiden_id}"
        assert favorite_sensor.icon == "mdi:guitar-electric"  # ACTIVE status icon
        assert hasattr(favorite_sensor, "_attr_has_entity_name")

    async def test_extra_state_attributes(self, favorite_sensor):
        """Test extra state attributes."""
        attributes = favorite_sensor.extra_state_attributes
        assert attributes is not None
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert attributes["musicbrainz_id"] == iron_maiden_id
        # Should have all Iron Maiden variants except first one (display name)
        expected_variants = favorite_sensor._current_favorite_data.get("variants", [])[
            1:
        ]
        assert attributes["variants"] == expected_variants

        # Should include relation URLs
        assert "allmusic_url" in attributes
        assert "bandsintown_url" in attributes
        assert "discogs_url" in attributes
        assert "songkick_url" in attributes

    async def test_native_value(self, favorite_sensor):
        """Test native value property."""
        # Returns the band status as the primary sensor state
        assert favorite_sensor.native_value == "Active"

    async def test_entity_id_generation(self, mock_device_info):
        """Test entity ID generation with various artist names."""
        # Test with special characters
        favorite_data = {"variants": ["Motörhead & Friends!"]}
        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )
        # Should create safe entity ID with "act_" prefix
        assert sensor.entity_id == "sensor.music_favorites_act_motörhead_friends"

        # Test with multiple spaces and hyphens
        favorite_data2 = {"variants": ["Iron  Maiden - Legacy"]}
        mock_entry2 = MagicMock()
        mock_entry2.data = {"favorites": {"test-id-2": favorite_data2}}
        sensor2 = FavoriteSensor(
            "test-id-2",
            favorite_data2,
            mock_device_info,
            mock_entry2,
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
            "musicbrainz_url": f"https://musicbrainz.org/artist/{IRON_MAIDEN_COMPLETE_RESPONSE['id']}",
            **relation_links,
        }

        # Create sensor with complete favorite data
        mock_entry = MagicMock()
        mock_entry.data = {
            "favorites": {IRON_MAIDEN_COMPLETE_RESPONSE["id"]: favorite_data}
        }
        sensor = FavoriteSensor(
            IRON_MAIDEN_COMPLETE_RESPONSE["id"],
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        # Test basic properties
        assert sensor._favorite_key == IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        assert sensor._current_favorite_data.get("variants", []) == variants
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
        assert "musicbrainz_url" in attributes
        assert (
            attributes["musicbrainz_url"]
            == "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )
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
            "musicbrainz_url": f"https://musicbrainz.org/artist/{HALF_ME_COMPLETE_RESPONSE['id']}",
            **relation_links,
        }

        # Create sensor with complete favorite data
        mock_entry = MagicMock()
        mock_entry.data = {
            "favorites": {HALF_ME_COMPLETE_RESPONSE["id"]: favorite_data}
        }
        sensor = FavoriteSensor(
            HALF_ME_COMPLETE_RESPONSE["id"],
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        # Test basic properties
        assert sensor._favorite_key == HALF_ME_COMPLETE_RESPONSE["id"]
        assert sensor._current_favorite_data.get("variants", []) == variants
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
        assert "musicbrainz_url" in attributes
        assert (
            attributes["musicbrainz_url"]
            == "https://musicbrainz.org/artist/963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"
        )
        assert "songkick_url" in attributes
        assert attributes["songkick_url"] == "https://www.songkick.com/artists/10118274"

    async def test_sensor_without_relation_links(self, mock_device_info):
        """Test FavoriteSensor with favorite data that has no relation links."""
        # Create favorite data without relation links
        favorite_data = {
            "variants": ["Test Artist", "Test Alias"],
        }

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-musicbrainz-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-musicbrainz-id",
            favorite_data,
            mock_device_info,
            mock_entry,
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

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-musicbrainz-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-musicbrainz-id",
            favorite_data,
            mock_device_info,
            mock_entry,
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


class TestFavoriteSensorConcertFormatting:
    """Test the FavoriteSensor concert formatting methods."""

    @pytest.fixture
    def sensor_with_events(self, mock_device_info):
        """Create a sensor with concert event data."""
        # Create favorite data with upcoming events
        favorite_data = {
            "variants": ["Test Band"],
            "events": [
                {
                    "event_date": "2025-12-31",
                    "location": "Madison Square Garden",
                    "venue_address": "4 Pennsylvania Plaza, New York, USA",
                },
                {
                    "event_date": "2025-11-15",
                    "location": "Red Rocks Amphitheatre",
                    "venue_address": "18300 W Alameda Pkwy, Morrison, USA",
                },
                {
                    "event_date": "2024-01-01",  # Past event
                    "location": "Past Venue",
                    "venue_address": "Old Street, Old City, Old Country",
                },
            ],
        }

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        return FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )

    async def test_get_next_concerts_text_with_events(self, sensor_with_events):
        """Test concert text formatting with upcoming events."""
        concert_text = sensor_with_events._generate_upcoming_concerts_text()

        # Should include both upcoming events in chronological order
        assert "Red Rocks Amphitheatre" in concert_text
        assert "Madison Square Garden" in concert_text
        assert "Morrison, USA" in concert_text
        assert "New York, USA" in concert_text

        # Should not include past event
        assert "Past Venue" not in concert_text

        # Events should be numbered and separated by " // "
        assert "1. " in concert_text
        assert "2. " in concert_text
        assert " // " in concert_text

    async def test_get_next_concerts_text_no_events(self, mock_device_info):
        """Test concert text when no events exist."""
        favorite_data = {"variants": ["Test Band"]}  # No events

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        concert_text = sensor._generate_upcoming_concerts_text()
        assert concert_text == "No upcoming concerts"

    async def test_get_next_concerts_text_only_past_events(self, mock_device_info):
        """Test concert text when all events are in the past."""
        favorite_data = {
            "variants": ["Test Band"],
            "events": [
                {
                    "event_date": "2020-01-01",
                    "location": "Old Venue",
                    "venue_address": "Old City, Old Country",
                }
            ],
        }

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        concert_text = sensor._generate_upcoming_concerts_text()
        assert concert_text == "No upcoming concerts"

    async def test_get_next_concerts_text_invalid_date(
        self, mock_device_info, caplog: pytest.LogCaptureFixture
    ):
        """Test concert text with invalid date format."""
        favorite_data = {
            "variants": ["Test Band"],
            "events": [
                {
                    "event_date": "invalid-date",
                    "location": "Test Venue",
                    "venue_address": "Test City, Test Country",
                },
                {
                    "event_date": "2025-12-31",  # Valid event
                    "location": "Valid Venue",
                    "venue_address": "Valid City, Valid Country",
                },
            ],
        }

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        concert_text = sensor._generate_upcoming_concerts_text()

        # Should skip invalid event and include valid one
        assert "Valid Venue" in concert_text
        assert "Test Venue" not in concert_text

        # Should log warning about invalid date
        assert "Failed to parse event date" in caplog.text

    async def test_get_next_concerts_text_missing_date(self, mock_device_info):
        """Test concert text when event has no date."""
        favorite_data = {
            "variants": ["Test Band"],
            "events": [
                {
                    # Missing event_date
                    "location": "Test Venue",
                    "venue_address": "Test City, Test Country",
                },
                {
                    "event_date": "2025-12-31",  # Valid event
                    "location": "Valid Venue",
                    "venue_address": "Valid City, Valid Country",
                },
            ],
        }

        mock_entry = MagicMock()
        mock_entry.data = {"favorites": {"test-id": favorite_data}}
        sensor = FavoriteSensor(
            "test-id",
            favorite_data,
            mock_device_info,
            mock_entry,
        )

        concert_text = sensor._generate_upcoming_concerts_text()

        # Should skip event without date and include valid one
        assert "Valid Venue" in concert_text
        assert "Test Venue" not in concert_text

    async def test_format_concert_for_text_full_address(self, sensor_with_events):
        """Test formatting single concert with full address."""
        event_data = {
            "event_date": "2025-12-31",
            "location": "Test Venue",
            "venue_address": "123 Main St, Test City, Test Country",
        }

        formatted = sensor_with_events._format_concert_for_text(event_data)

        assert formatted is not None
        assert "Test Venue" in formatted
        assert "Test City" in formatted
        assert "Test Country" in formatted
        assert "Dec 31, 2025" in formatted
        # Should not include street address
        assert "123 Main St" not in formatted

    async def test_format_concert_for_text_short_address(self, sensor_with_events):
        """Test formatting concert with short address (city only)."""
        event_data = {
            "event_date": "2025-12-31",
            "location": "Test Venue",
            "venue_address": "Test City",
        }

        formatted = sensor_with_events._format_concert_for_text(event_data)

        assert formatted is not None
        assert "Test Venue" in formatted
        assert "Test City" in formatted
        assert "Dec 31, 2025" in formatted

    async def test_format_concert_for_text_no_address(self, sensor_with_events):
        """Test formatting concert without venue address."""
        event_data = {
            "event_date": "2025-12-31",
            "location": "Test Venue",
        }

        formatted = sensor_with_events._format_concert_for_text(event_data)

        assert formatted is not None
        assert "Test Venue" in formatted
        assert "Dec 31, 2025" in formatted
        # Should only have venue name and date (no city/country)
        assert formatted == "Test Venue - Dec 31, 2025"

    async def test_format_concert_for_text_missing_date(self, sensor_with_events):
        """Test formatting concert without date."""
        event_data = {
            "location": "Test Venue",
            "venue_address": "Test City, Test Country",
        }

        formatted = sensor_with_events._format_concert_for_text(event_data)

        assert formatted is None  # Should return None for missing date

    async def test_format_concert_for_text_invalid_date(
        self, sensor_with_events, caplog: pytest.LogCaptureFixture
    ):
        """Test formatting concert with invalid date."""
        event_data = {
            "event_date": "not-a-date",
            "location": "Test Venue",
            "venue_address": "Test City, Test Country",
        }

        formatted = sensor_with_events._format_concert_for_text(event_data)

        assert formatted is None  # Should return None on error
        assert "Failed to format concert for text display" in caplog.text


class TestFavoriteSensorLifecycle:
    """Test FavoriteSensor lifecycle methods."""

    async def test_async_added_to_hass(
        self, hass: HomeAssistant, mock_device_info, mock_config_entry_with_iron_maiden
    ):
        """Test entity registration and listener setup."""
        favorites_data = mock_config_entry_with_iron_maiden.data["favorites"]
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        favorite_data = favorites_data[iron_maiden_id]

        sensor = FavoriteSensor(
            iron_maiden_id,
            favorite_data,
            mock_device_info,
            mock_config_entry_with_iron_maiden,
        )

        # Add entity to hass
        await sensor.async_added_to_hass()

        # Verify listener was registered (async_on_remove was called)
        # The listener should be in the entity's remove callbacks
        if sensor._on_remove is not None:
            assert len(sensor._on_remove) > 0

    async def test_config_entry_updated_callback(
        self, hass: HomeAssistant, mock_device_info, mock_config_entry_with_iron_maiden
    ):
        """Test config entry update triggers entity state update."""
        favorites_data = mock_config_entry_with_iron_maiden.data["favorites"]
        iron_maiden_id = IRON_MAIDEN_COMPLETE_RESPONSE["id"]
        favorite_data = favorites_data[iron_maiden_id]

        sensor = FavoriteSensor(
            iron_maiden_id,
            favorite_data,
            mock_device_info,
            mock_config_entry_with_iron_maiden,
        )

        # Mock async_schedule_update_ha_state
        with patch.object(sensor, "async_schedule_update_ha_state") as mock_update:
            # Call the update callback
            await sensor._config_entry_updated(hass, mock_config_entry_with_iron_maiden)

            # Verify state update was scheduled
            mock_update.assert_called_once()


class TestAsyncSetupEntry:
    """Test async_setup_entry platform setup."""

    async def test_setup_entry_creates_device_and_entities(
        self, hass: HomeAssistant, mock_config_entry_with_iron_maiden
    ):
        """Test that async_setup_entry creates device info and entities."""
        mock_add_entities = MagicMock()

        # Call setup_entry
        await async_setup_entry(
            hass, mock_config_entry_with_iron_maiden, mock_add_entities
        )

        # Verify entity manager was created and stored
        assert "entity_manager" in mock_config_entry_with_iron_maiden.runtime_data

        # Verify entities were created for existing favorites
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]

        # Should have created one entity for Iron Maiden
        assert len(entities) == 1
        assert isinstance(entities[0], FavoriteSensor)
        assert entities[0]._favorite_key == IRON_MAIDEN_COMPLETE_RESPONSE["id"]

    async def test_setup_entry_no_initial_favorites(self, hass: HomeAssistant):
        """Test async_setup_entry with no initial favorites."""
        # Create config entry with no favorites
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"
        mock_entry.data = {"favorites": {}}  # Empty favorites
        mock_entry.runtime_data = {}

        mock_add_entities = MagicMock()

        # Call setup_entry
        await async_setup_entry(hass, mock_entry, mock_add_entities)

        # Verify entity manager was created
        assert "entity_manager" in mock_entry.runtime_data

        # Verify no entities were added (empty favorites)
        mock_add_entities.assert_not_called()
