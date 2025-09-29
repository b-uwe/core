"""Test Music Favorites calendar utilities."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.calendar_utils import (
    _notify_calendar_entity,
    _should_include_event_by_distance,
    calculate_approximate_distance,
    create_calendar_device_info,
    update_filtered_calendar_cache,
)
from homeassistant.components.music_favorites.const import DOMAIN, VERSION
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class TestCalculateApproximateDistance:
    """Test the calculate_approximate_distance function."""

    def test_zero_distance(self) -> None:
        """Test distance calculation for the same point."""
        distance = calculate_approximate_distance(52.5200, 13.4050, 52.5200, 13.4050)
        assert distance == 0.0

    def test_approximate_distance_calculation(self) -> None:
        """Test distance calculation between known points."""
        # Berlin to Hamburg (approximately 255 km)
        berlin_lat, berlin_lon = 52.5200, 13.4050
        hamburg_lat, hamburg_lon = 53.5511, 9.9937

        distance = calculate_approximate_distance(
            berlin_lat, berlin_lon, hamburg_lat, hamburg_lon
        )

        # Should be approximately 255 km (allowing some tolerance for approximation)
        assert 250 <= distance <= 260

    def test_negative_coordinates(self) -> None:
        """Test distance calculation with negative coordinates."""
        # Test points in different hemispheres
        distance = calculate_approximate_distance(
            40.7128, -74.0060, -33.8688, 151.2093
        )  # NYC to Sydney

        # Should be a very large distance (approx 15,990 km)
        assert distance > 15000

    def test_distance_symmetry(self) -> None:
        """Test that distance calculation is symmetric."""
        lat1, lon1 = 52.5200, 13.4050  # Berlin
        lat2, lon2 = 48.8566, 2.3522  # Paris

        distance1 = calculate_approximate_distance(lat1, lon1, lat2, lon2)
        distance2 = calculate_approximate_distance(lat2, lon2, lat1, lon1)  # pylint: disable=arguments-out-of-order

        assert distance1 == distance2

    def test_absolute_distance(self) -> None:
        """Test that distance is always positive."""
        # Test with points that would give negative intermediate results
        distance = calculate_approximate_distance(0, 0, -10, -10)
        assert distance > 0

    def test_longitude_correction_near_equator(self) -> None:
        """Test longitude distance correction near equator."""
        # Near equator (latitude ≈ 0), longitude degrees should be close to 111 km
        distance = calculate_approximate_distance(
            0, 0, 0, 1
        )  # 1 degree longitude at equator

        # Should be approximately 111 km
        assert 110 <= distance <= 112

    def test_longitude_correction_near_poles(self) -> None:
        """Test longitude distance correction near poles."""
        # Near north pole (latitude ≈ 89°), longitude degrees should be much smaller
        distance = calculate_approximate_distance(
            89, 0, 89, 1
        )  # 1 degree longitude at 89° north

        # Should be much less than 111 km due to cos(89°) ≈ 0.017
        assert distance < 10


class TestCreateCalendarDeviceInfo:
    """Test the create_calendar_device_info function."""

    def test_device_info_creation(self) -> None:
        """Test device info creation with valid entry ID."""
        entry_id = "test_entry_123"

        device_info = create_calendar_device_info(entry_id)

        assert device_info["identifiers"] == {(DOMAIN, f"{entry_id}_calendar")}
        assert device_info["name"] == "Concert Calendar"
        assert device_info["manufacturer"] == "Music Favorites Integration"
        assert device_info["model"] == "Event Calendar"
        assert device_info["sw_version"] == VERSION
        assert (
            device_info["configuration_url"]
            == f"homeassistant://config/integrations/integration/{DOMAIN}"
        )

    def test_device_info_unique_identifiers(self) -> None:
        """Test that different entry IDs create unique device identifiers."""
        entry_id_1 = "entry_1"
        entry_id_2 = "entry_2"

        device_info_1 = create_calendar_device_info(entry_id_1)
        device_info_2 = create_calendar_device_info(entry_id_2)

        assert device_info_1["identifiers"] != device_info_2["identifiers"]
        assert (DOMAIN, f"{entry_id_1}_calendar") in device_info_1["identifiers"]
        assert (DOMAIN, f"{entry_id_2}_calendar") in device_info_2["identifiers"]


class TestShouldIncludeEventByDistance:
    """Test the _should_include_event_by_distance function."""

    def test_no_distance_limit(self) -> None:
        """Test that events are included when no distance limit is set."""
        event = {
            "text": "Test Event",
            "latitude": 52.5200,
            "longitude": 13.4050,
        }

        result = _should_include_event_by_distance(event, None, 40.7128, -74.0060)
        assert result is True

    def test_no_ha_location(self) -> None:
        """Test that events are included when HA location is not configured."""
        event = {
            "text": "Test Event",
            "latitude": 52.5200,
            "longitude": 13.4050,
        }

        # Test with None latitude
        result = _should_include_event_by_distance(event, 100, None, -74.0060)
        assert result is True

        # Test with None longitude
        result = _should_include_event_by_distance(event, 100, 40.7128, None)
        assert result is True

    def test_no_event_coordinates(self) -> None:
        """Test that events without coordinates are included."""
        # Event without latitude
        event_no_lat = {
            "text": "Test Event",
            "longitude": 13.4050,
        }
        result = _should_include_event_by_distance(event_no_lat, 100, 40.7128, -74.0060)
        assert result is True

        # Event without longitude
        event_no_lon = {
            "text": "Test Event",
            "latitude": 52.5200,
        }
        result = _should_include_event_by_distance(event_no_lon, 100, 40.7128, -74.0060)
        assert result is True

        # Event without both coordinates
        event_no_coords = {"text": "Test Event"}
        result = _should_include_event_by_distance(
            event_no_coords, 100, 40.7128, -74.0060
        )
        assert result is True

    def test_event_within_distance_limit(self) -> None:
        """Test event within distance limit is included."""
        # Berlin coordinates
        event = {
            "text": "Test Event",
            "latitude": 52.5200,
            "longitude": 13.4050,
        }

        # HA location also in Berlin (very close)
        result = _should_include_event_by_distance(event, 100, 52.5201, 13.4051)
        assert result is True

    def test_event_beyond_distance_limit(self) -> None:
        """Test event beyond distance limit is filtered out."""
        # Berlin coordinates
        event = {
            "text": "Test Event",
            "latitude": 52.5200,
            "longitude": 13.4050,
        }

        # HA location in NYC (very far)
        result = _should_include_event_by_distance(event, 100, 40.7128, -74.0060)
        assert result is False

    def test_event_exactly_at_distance_limit(self) -> None:
        """Test event exactly at distance limit is included."""
        # Use known coordinates with approximately 50km distance
        event = {
            "text": "Test Event",
            "latitude": 52.5200,
            "longitude": 13.4050,
        }

        # Calculate the actual distance first
        distance = calculate_approximate_distance(52.5200, 13.4050, 52.0000, 13.4050)

        # Set limit to exactly that distance
        result = _should_include_event_by_distance(event, distance, 52.0000, 13.4050)
        assert result is True

    def test_invalid_event_coordinates(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test handling of invalid event coordinates."""
        event = {
            "text": "Test Event",
            "latitude": "invalid",
            "longitude": "also_invalid",
        }

        with caplog.at_level(logging.ERROR):
            result = _should_include_event_by_distance(event, 100, 40.7128, -74.0060)

        # Should include event when distance calculation fails
        assert result is True
        assert "Failed to calculate distance for event 'Test Event'" in caplog.text

    def test_none_event_coordinates(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test handling of None event coordinates."""
        event = {
            "text": "Test Event",
            "latitude": None,
            "longitude": None,
        }

        result = _should_include_event_by_distance(event, 100, 40.7128, -74.0060)

        # Should include event (handled before distance calculation)
        assert result is True


class TestNotifyCalendarEntity:
    """Test the _notify_calendar_entity function."""

    async def test_notify_existing_calendar_entity(self) -> None:
        """Test notifying an existing calendar entity."""
        # Create mock config entry with calendar entity
        mock_calendar_entity = MagicMock()
        mock_entry = MagicMock()
        mock_entry.runtime_data = {"calendar_entity": mock_calendar_entity}

        # Create mock hass
        hass = MagicMock(spec=HomeAssistant)

        await _notify_calendar_entity(hass, mock_entry)

        # Verify the calendar entity was notified
        mock_calendar_entity.async_write_ha_state.assert_called_once()

    async def test_notify_missing_calendar_entity(self) -> None:
        """Test handling when calendar entity is not registered."""
        # Create mock config entry without calendar entity
        mock_entry = MagicMock()
        mock_entry.runtime_data = {}

        # Create mock hass
        hass = MagicMock(spec=HomeAssistant)

        # Should not raise an exception
        await _notify_calendar_entity(hass, mock_entry)


class TestUpdateFilteredCalendarCache:
    """Test the update_filtered_calendar_cache function."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry for testing."""
        return MockConfigEntry(
            domain=DOMAIN,
            title="Music Favorites",
            data={
                "favorites": {
                    "artist1": {
                        "variants": ["Test Artist 1"],
                        "events": [
                            {
                                "text": "Test Event 1",
                                "latitude": 52.5200,
                                "longitude": 13.4050,
                                "event_date": "2025-12-01",
                            }
                        ],
                    },
                    "artist2": {
                        "variants": ["Test Artist 2"],
                        "events": [
                            {
                                "text": "Test Event 2",
                                "latitude": 40.7128,
                                "longitude": -74.0060,
                                "event_date": "2025-12-15",
                            }
                        ],
                    },
                },
                "distance_filter": 100,
            },
            unique_id="music_favorites_unique_id",
        )

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        # Need to create a mock config object since spec doesn't include attributes
        mock_config = MagicMock()
        mock_config.latitude = 52.5200  # Berlin coordinates
        mock_config.longitude = 13.4050
        hass.config = mock_config
        return hass

    async def test_update_cache_basic_functionality(
        self, mock_hass, mock_config_entry
    ) -> None:
        """Test basic cache update functionality."""
        # Add runtime_data to mock entry
        mock_config_entry.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ) as mock_notify:
            await update_filtered_calendar_cache(mock_hass, mock_config_entry)

        # Verify cache was populated
        assert "filtered_calendar_events" in mock_config_entry.runtime_data
        cached_events = mock_config_entry.runtime_data["filtered_calendar_events"]

        # Should have events with performer info added
        assert (
            len(cached_events) >= 1
        )  # At least one event should be within 100km of Berlin

        for event in cached_events:
            assert "performer_name" in event
            assert "musicbrainz_id" in event
            assert event["performer_name"] in ["Test Artist 1", "Test Artist 2"]

        # Verify notification was called
        mock_notify.assert_called_once_with(mock_hass, mock_config_entry)

    async def test_update_cache_no_distance_limit(self, mock_hass) -> None:
        """Test cache update with no distance limit."""
        # Create config entry with no distance limit
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Music Favorites",
            data={
                "favorites": {
                    "artist1": {
                        "variants": ["Test Artist 1"],
                        "events": [
                            {
                                "text": "Test Event 1",
                                "latitude": 52.5200,
                                "longitude": 13.4050,
                                "event_date": "2025-12-01",
                            }
                        ],
                    },
                    "artist2": {
                        "variants": ["Test Artist 2"],
                        "events": [
                            {
                                "text": "Test Event 2",
                                "latitude": 40.7128,
                                "longitude": -74.0060,
                                "event_date": "2025-12-15",
                            }
                        ],
                    },
                },
                "distance_filter": None,  # No distance limit
            },
            unique_id="music_favorites_unique_id",
        )
        mock_config_entry.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, mock_config_entry)

        cached_events = mock_config_entry.runtime_data["filtered_calendar_events"]

        # All events should be included (no distance filtering)
        assert len(cached_events) == 2

        performer_names = {event["performer_name"] for event in cached_events}
        assert performer_names == {"Test Artist 1", "Test Artist 2"}

    async def test_update_cache_distance_filtering(self, mock_hass) -> None:
        """Test cache update with distance filtering."""
        # Create config entry with small distance limit
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Music Favorites",
            data={
                "favorites": {
                    "artist1": {
                        "variants": ["Test Artist 1"],
                        "events": [
                            {
                                "text": "Test Event 1",
                                "latitude": 52.5200,
                                "longitude": 13.4050,
                                "event_date": "2025-12-01",
                            }
                        ],
                    },
                    "artist2": {
                        "variants": ["Test Artist 2"],
                        "events": [
                            {
                                "text": "Test Event 2",
                                "latitude": 40.7128,
                                "longitude": -74.0060,
                                "event_date": "2025-12-15",
                            }
                        ],
                    },
                },
                "distance_filter": 1,  # 1 km - very small limit
            },
            unique_id="music_favorites_unique_id",
        )
        mock_config_entry.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, mock_config_entry)

        cached_events = mock_config_entry.runtime_data["filtered_calendar_events"]

        # Only Berlin event should be included (NYC event filtered out)
        assert len(cached_events) == 1
        assert cached_events[0]["performer_name"] == "Test Artist 1"
        assert cached_events[0]["text"] == "Test Event 1"

    async def test_update_cache_no_ha_location(self, mock_config_entry) -> None:
        """Test cache update when HA location is not configured."""
        # Create hass without location
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_config = MagicMock()
        mock_config.latitude = None
        mock_config.longitude = None
        mock_hass.config = mock_config

        mock_config_entry.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, mock_config_entry)

        cached_events = mock_config_entry.runtime_data["filtered_calendar_events"]

        # All events should be included (no location for filtering)
        assert len(cached_events) == 2

    async def test_update_cache_empty_favorites(self, mock_hass) -> None:
        """Test cache update with empty favorites."""
        empty_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"favorites": {}, "distance_filter": 100},
        )
        empty_entry.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, empty_entry)

        cached_events = empty_entry.runtime_data["filtered_calendar_events"]
        assert len(cached_events) == 0

    async def test_update_cache_missing_favorites_key(self, mock_hass) -> None:
        """Test cache update with missing favorites key."""
        entry_no_favorites = MockConfigEntry(
            domain=DOMAIN,
            data={"distance_filter": 100},  # No favorites key
        )
        entry_no_favorites.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, entry_no_favorites)

        cached_events = entry_no_favorites.runtime_data["filtered_calendar_events"]
        assert len(cached_events) == 0

    async def test_update_cache_events_without_coordinates(self, mock_hass) -> None:
        """Test cache update with events that don't have coordinates."""
        entry_no_coords = MockConfigEntry(
            domain=DOMAIN,
            data={
                "favorites": {
                    "artist1": {
                        "variants": ["Test Artist"],
                        "events": [
                            {
                                "text": "Test Event No Coords",
                                "event_date": "2025-12-01",
                                # No latitude/longitude
                            }
                        ],
                    }
                },
                "distance_filter": 100,
            },
        )
        entry_no_coords.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, entry_no_coords)

        cached_events = entry_no_coords.runtime_data["filtered_calendar_events"]

        # Event without coordinates should be included
        assert len(cached_events) == 1
        assert cached_events[0]["text"] == "Test Event No Coords"

    async def test_update_cache_default_distance_filter(self, mock_hass) -> None:
        """Test cache update uses default distance filter when missing."""
        entry_no_distance = MockConfigEntry(
            domain=DOMAIN,
            data={
                "favorites": {
                    "artist1": {
                        "variants": ["Test Artist"],
                        "events": [
                            {
                                "text": "Test Event",
                                "latitude": 52.5200,
                                "longitude": 13.4050,
                                "event_date": "2025-12-01",
                            }
                        ],
                    }
                },
                # No distance_filter key
            },
        )
        entry_no_distance.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, entry_no_distance)

        cached_events = entry_no_distance.runtime_data["filtered_calendar_events"]

        # Should use DEFAULT_MAX_DISTANCE_KM and include the Berlin event
        assert len(cached_events) == 1

    async def test_update_cache_unknown_performer_fallback(self, mock_hass) -> None:
        """Test cache update handles favorites without variants."""
        entry_no_variants = MockConfigEntry(
            domain=DOMAIN,
            data={
                "favorites": {
                    "artist1": {
                        # No variants key
                        "events": [
                            {
                                "text": "Test Event",
                                "latitude": 52.5200,
                                "longitude": 13.4050,
                                "event_date": "2025-12-01",
                            }
                        ],
                    }
                },
                "distance_filter": 100,
            },
        )
        entry_no_variants.runtime_data = {}

        with patch(
            "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
        ):
            await update_filtered_calendar_cache(mock_hass, entry_no_variants)

        cached_events = entry_no_variants.runtime_data["filtered_calendar_events"]

        # Should use "Unknown Artist" as performer name
        assert len(cached_events) == 1
        assert cached_events[0]["performer_name"] == "Unknown Artist"

    async def test_update_cache_logging(
        self, mock_hass, mock_config_entry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test cache update logging."""
        mock_config_entry.runtime_data = {}

        with (
            caplog.at_level(logging.DEBUG),
            patch(
                "homeassistant.components.music_favorites.calendar_utils._notify_calendar_entity"
            ),
        ):
            await update_filtered_calendar_cache(mock_hass, mock_config_entry)

        # Verify debug logs are present
        assert "Updating filtered calendar events cache" in caplog.text
        assert "Distance filter: 100 km" in caplog.text
        assert "Distance filtering:" in caplog.text
