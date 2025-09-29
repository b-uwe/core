"""Test Music Favorites calendar platform."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.bandsintown import extract_music_events
from homeassistant.components.music_favorites.calendar import (
    MusicFavoritesCalendar,
    async_setup_entry,
)
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.models import extract_pure_event_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .fixtures.bandsintown_responses import VULVODYNIA_EVENTS_LDJSON

from tests.common import MockConfigEntry


@pytest.fixture
def processed_vulvodynia_events():
    """Process Vulvodynia fixture data through the real pipeline."""
    # Step 1: Extract music events from LD+JSON (as bandsintown.py does)
    music_events = extract_music_events(VULVODYNIA_EVENTS_LDJSON)

    # Step 2: Process through extract_pure_event_data (as models.py does)
    return extract_pure_event_data(music_events)


@pytest.fixture
def mock_config_entry_with_events(processed_vulvodynia_events):
    """Create a mock config entry with properly processed event data."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {
                "vulvodynia-id": {
                    "variants": ["Vulvodynia"],
                    "status": "Active",
                    "events": processed_vulvodynia_events,
                },
                "test-artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    "events": [],  # No events for this artist
                },
            }
        },
        unique_id="music_favorites",
    )


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test setting up calendar entity."""
    mock_config_entry_with_events.add_to_hass(hass)

    mock_add_entities = MagicMock()

    await async_setup_entry(hass, mock_config_entry_with_events, mock_add_entities)

    # Verify entity was added
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], MusicFavoritesCalendar)

    # Verify device info
    calendar_entity = entities[0]
    device_info = calendar_entity.device_info
    assert device_info["name"] == "Concert Calendar"
    assert device_info["manufacturer"] == "Music Favorites Integration"
    assert device_info["model"] == "Event Calendar"
    assert (
        DOMAIN,
        f"{mock_config_entry_with_events.entry_id}_calendar",
    ) in device_info["identifiers"]


def test_calendar_entity_initialization(mock_config_entry_with_events) -> None:
    """Test calendar entity initialization."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    assert calendar_entity._attr_name == "Concert Calendar"
    assert (
        calendar_entity._attr_unique_id
        == f"{mock_config_entry_with_events.entry_id}_calendar"
    )
    assert calendar_entity._attr_device_info == device_info
    assert calendar_entity._attr_has_entity_name is True


async def test_async_added_to_hass(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test entity added to hass sets up update listener."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)
    calendar_entity.hass = hass

    # Mock async_on_remove to verify listener is added
    mock_on_remove = MagicMock()
    calendar_entity.async_on_remove = mock_on_remove

    await calendar_entity.async_added_to_hass()

    # Verify update listener was added
    mock_on_remove.assert_called_once()


async def test_config_entry_updated(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test config entry update handler."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)
    calendar_entity.hass = hass

    # Mock async_write_ha_state
    mock_write_state = MagicMock()
    calendar_entity.async_write_ha_state = mock_write_state

    await calendar_entity._config_entry_updated(hass, mock_config_entry_with_events)

    # Verify state was written
    mock_write_state.assert_called_once()


def test_get_all_events(
    mock_config_entry_with_events, processed_vulvodynia_events
) -> None:
    """Test getting all events from favorites."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    all_events = calendar_entity._get_all_events()

    # Should have 2 events from Vulvodynia (processed from fixtures)
    assert len(all_events) == 2

    # Check first event has performer info added
    vulvodynia_event = all_events[0]
    assert vulvodynia_event["performer_name"] == "Vulvodynia"
    assert vulvodynia_event["musicbrainz_id"] == "vulvodynia-id"

    # Verify it has the processed event data from fixtures
    assert "event_date" in vulvodynia_event
    assert "venue_time" in vulvodynia_event
    assert "venue_time_display" in vulvodynia_event

    # Check that original fixture data flowed through correctly
    assert vulvodynia_event["text"] == VULVODYNIA_EVENTS_LDJSON[0]["name"]
    assert vulvodynia_event["url"] == VULVODYNIA_EVENTS_LDJSON[0]["url"]


def test_get_all_events_empty_favorites() -> None:
    """Test getting events when no favorites exist."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"favorites": {}},
        unique_id="music_favorites",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    all_events = calendar_entity._get_all_events()
    assert all_events == []


def test_get_all_events_no_events_data() -> None:
    """Test getting events when favorites exist but have no events."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    # No events key
                }
            }
        },
        unique_id="music_favorites",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    all_events = calendar_entity._get_all_events()
    assert all_events == []


def test_get_all_events_no_variants() -> None:
    """Test getting events when favorite has no variants."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "status": "Active",
                    "events": [
                        {
                            "text": "Concert",
                            "event_date": "2025-12-01",
                        }
                    ],
                    # No variants key
                }
            }
        },
        unique_id="music_favorites",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    all_events = calendar_entity._get_all_events()
    assert len(all_events) == 1
    assert all_events[0]["performer_name"] == "Unknown Artist"


def test_convert_to_calendar_event_complete(
    mock_config_entry_with_events, processed_vulvodynia_events
) -> None:
    """Test converting complete event data to CalendarEvent."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Use the first processed event from fixtures
    event_data = processed_vulvodynia_events[0].copy()
    event_data["performer_name"] = "Vulvodynia"
    event_data["musicbrainz_id"] = "vulvodynia-id"

    calendar_event = calendar_entity._convert_to_calendar_event(event_data)

    assert calendar_event is not None
    assert calendar_event.start == date(2025, 11, 25)  # From fixture
    assert calendar_event.end == date(
        2025, 11, 26
    )  # Standard all-day event behavior (exclusive end)
    assert calendar_event.summary == VULVODYNIA_EVENTS_LDJSON[0]["name"]  # From fixture
    assert "Concert by Vulvodynia" in calendar_event.description
    assert "6:00 PM venue local time" in calendar_event.description
    assert calendar_event.uid == "music_favorites_vulvodynia-id_2025-11-25"


def test_convert_to_calendar_event_minimal(mock_config_entry_with_events) -> None:
    """Test converting minimal event data to CalendarEvent."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    event_data = {
        "event_date": "2025-12-01",
        "musicbrainz_id": "test-id",
    }

    calendar_event = calendar_entity._convert_to_calendar_event(event_data)

    assert calendar_event is not None
    assert calendar_event.start == date(2025, 12, 1)
    assert calendar_event.end == date(
        2025, 12, 2
    )  # Standard all-day event behavior (exclusive end)
    assert calendar_event.summary == "Concert"  # Default when no text
    assert (
        calendar_event.description == "Concert by Unknown Artist"
    )  # Default performer
    assert calendar_event.location is None
    assert calendar_event.uid == "music_favorites_test-id_2025-12-01"


def test_convert_to_calendar_event_no_event_date(mock_config_entry_with_events) -> None:
    """Test converting event data without event_date returns None."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    event_data = {
        "text": "Concert",
        "performer_name": "Test Artist",
        # No event_date
    }

    calendar_event = calendar_entity._convert_to_calendar_event(event_data)
    assert calendar_event is None


def test_convert_to_calendar_event_invalid_date(mock_config_entry_with_events) -> None:
    """Test converting event data with invalid date returns None."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    event_data = {
        "text": "Concert",
        "event_date": "invalid-date",
        "performer_name": "Test Artist",
    }

    with patch(
        "homeassistant.components.music_favorites.calendar._LOGGER"
    ) as mock_logger:
        calendar_event = calendar_entity._convert_to_calendar_event(event_data)

        assert calendar_event is None
        mock_logger.warning.assert_called_once()
        assert "Failed to convert event to calendar event" in str(
            mock_logger.warning.call_args
        )


def test_event_property_upcoming_events(mock_config_entry_with_events) -> None:
    """Test event property returns next upcoming event."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Mock dt_util.now() to return a time before all events
    fixed_now = datetime(2025, 11, 1, tzinfo=dt_util.UTC)
    with patch(
        "homeassistant.components.music_favorites.calendar.dt_util.now",
        return_value=fixed_now,
    ):
        next_event = calendar_entity.event

    assert next_event is not None
    assert next_event.start == date(
        2025, 11, 25
    )  # Should be the earliest from fixtures
    assert VULVODYNIA_EVENTS_LDJSON[0]["name"] in next_event.summary


def test_event_property_no_upcoming_events(mock_config_entry_with_events) -> None:
    """Test event property returns None when no upcoming events."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Mock dt_util.now() to return a time after all events
    fixed_now = datetime(2026, 1, 1, tzinfo=dt_util.UTC)
    with patch(
        "homeassistant.components.music_favorites.calendar.dt_util.now",
        return_value=fixed_now,
    ):
        next_event = calendar_entity.event

    assert next_event is None


def test_event_property_empty_favorites() -> None:
    """Test event property with empty favorites."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"favorites": {}},
        unique_id="music_favorites",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    next_event = calendar_entity.event
    assert next_event is None


async def test_async_get_events(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test getting events within a date range."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Get events for November 2025 (covers the fixture events)
    start_date = datetime(2025, 11, 1, tzinfo=dt_util.UTC)
    end_date = datetime(2025, 12, 1, tzinfo=dt_util.UTC)

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    # Should return 2 events (both Vulvodynia events from fixtures)
    assert len(events) == 2
    assert events[0].start == date(2025, 11, 25)  # From VULVODYNIA_EVENTS_LDJSON[0]
    assert events[1].start == date(2025, 11, 28)  # From VULVODYNIA_EVENTS_LDJSON[1]

    # Events should be sorted by start time
    assert events[0].start <= events[1].start


async def test_async_get_events_no_overlap(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test getting events with no date range overlap."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Get events for a time period with no events
    start_date = datetime(2025, 10, 1, tzinfo=dt_util.UTC)
    end_date = datetime(2025, 10, 31, tzinfo=dt_util.UTC)

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    assert len(events) == 0


async def test_async_get_events_invalid_event_data(hass: HomeAssistant) -> None:
    """Test getting events when some event data is invalid."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "events": [
                        {
                            "text": "Valid Event",
                            "event_date": "2025-11-25",
                        },
                        {
                            "text": "Invalid Event",
                            "event_date": "invalid-date",  # Invalid date
                        },
                        {
                            "text": "Missing Date Event",
                            # No event_date
                        },
                    ],
                },
            }
        },
        unique_id="music_favorites",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    start_date = datetime(2025, 11, 1, tzinfo=dt_util.UTC)
    end_date = datetime(2025, 12, 1, tzinfo=dt_util.UTC)

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    # Should only return the valid event (invalid ones filtered out)
    assert len(events) == 1
    assert events[0].summary == "Valid Event"
