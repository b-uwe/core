"""Test Music Favorites calendar platform."""

from datetime import datetime, timedelta
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
    """Process Vulvodynia fixture data through the real pipeline with dynamic future dates."""
    # Step 1: Extract music events from LD+JSON (as bandsintown.py does)
    music_events = extract_music_events(VULVODYNIA_EVENTS_LDJSON)

    # Step 2: Process through extract_pure_event_data (as models.py does)
    processed_events = extract_pure_event_data(music_events)

    # Step 3: Update with future dates to ensure tests always work
    base_future_date = datetime.now() + timedelta(days=30)

    for i, event in enumerate(processed_events):
        future_date = base_future_date + timedelta(
            days=i * 3
        )  # Space events 3 days apart
        event["event_date"] = future_date.strftime("%Y-%m-%d")

    return processed_events


@pytest.fixture
def mock_config_entry_with_events(processed_vulvodynia_events):
    """Create a mock config entry with properly processed event data."""
    entry = MockConfigEntry(
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
            },
            "distance_filter": 100,  # Default distance filter
        },
        unique_id="music_favorites",
    )
    # Set up runtime_data with cache that calendar entity expects
    entry.runtime_data = {
        "filtered_calendar_events": [
            {**event, "performer_name": "Vulvodynia", "musicbrainz_id": "vulvodynia-id"}
            for event in processed_vulvodynia_events
        ]
    }
    return entry


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
    assert device_info is not None
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

    assert calendar_entity._attr_name is None
    assert (
        calendar_entity._attr_unique_id
        == f"{mock_config_entry_with_events.entry_id}_calendar"
    )
    assert calendar_entity._attr_device_info == device_info
    assert calendar_entity._attr_has_entity_name is True


async def test_async_added_to_hass(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test entity added to hass sets up update listener and registers in runtime_data."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)
    calendar_entity.hass = hass

    # Mock async_on_remove to verify listener is added
    with patch.object(calendar_entity, "async_on_remove") as mock_on_remove:
        await calendar_entity.async_added_to_hass()

        # Verify update listener was added
        mock_on_remove.assert_called_once()

    # Verify calendar entity was registered in runtime_data
    assert (
        mock_config_entry_with_events.runtime_data["calendar_entity"] == calendar_entity
    )


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
    with patch.object(calendar_entity, "async_write_ha_state") as mock_write_state:
        await calendar_entity._config_entry_updated(hass, mock_config_entry_with_events)

        # Verify state was written
        mock_write_state.assert_called_once()


def test_get_all_events(
    mock_config_entry_with_events, processed_vulvodynia_events
) -> None:
    """Test getting all events from cache."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    all_events = calendar_entity._get_all_events()

    # Should have 2 events from cache (processed from fixtures)
    assert len(all_events) == 2

    # Check first event has performer info added (from cache)
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
    """Test getting events when cache is empty."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"favorites": {}, "distance_filter": 100},
        unique_id="music_favorites",
    )
    mock_entry.runtime_data = {"filtered_calendar_events": []}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    all_events = calendar_entity._get_all_events()
    assert all_events == []


def test_get_all_events_no_events_data() -> None:
    """Test getting events when cache has no events."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    # No events key
                }
            },
            "distance_filter": 100,
        },
        unique_id="music_favorites",
    )
    mock_entry.runtime_data = {"filtered_calendar_events": []}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    all_events = calendar_entity._get_all_events()
    assert all_events == []


def test_get_all_events_no_variants() -> None:
    """Test getting events from cache when performer name is unknown."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "status": "Active",
                    "events": [
                        {
                            "text": "Concert",
                            "event_date": (
                                datetime.now() + timedelta(days=30)
                            ).strftime("%Y-%m-%d"),
                        }
                    ],
                    # No variants key
                }
            },
            "distance_filter": 100,
        },
        unique_id="music_favorites",
    )
    # Simulate cache with unknown artist name
    mock_entry.runtime_data = {
        "filtered_calendar_events": [
            {
                "text": "Concert",
                "event_date": (datetime.now() + timedelta(days=30)).strftime(
                    "%Y-%m-%d"
                ),
                "performer_name": "Unknown Artist",
                "musicbrainz_id": "artist-id",
            }
        ]
    }

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
    # Verify dates match the processed fixture data (dynamic)
    expected_date_str = processed_vulvodynia_events[0]["event_date"]
    expected_date = datetime.strptime(expected_date_str, "%Y-%m-%d").date()
    assert calendar_event.start == expected_date
    assert calendar_event.end == expected_date + timedelta(
        days=1
    )  # Exclusive end date for all-day events
    assert calendar_event.summary == VULVODYNIA_EVENTS_LDJSON[0]["name"]  # From fixture
    assert calendar_event.description is not None
    assert "Concert by Vulvodynia" in calendar_event.description
    assert "6:00 PM venue local time" in calendar_event.description
    # Check that Bandsintown URL is included in description (cleaned of tracking parameters)
    expected_clean_url = (
        "https://www.bandsintown.com/e/1036117971-vulvodynia-at-o2-academy-islington"
    )
    assert expected_clean_url in calendar_event.description
    # Ensure the tracking parameter is NOT in the description
    assert "came_from=" not in calendar_event.description
    expected_uid = f"music_favorites_vulvodynia-id_{expected_date_str}"
    assert calendar_event.uid == expected_uid


def test_convert_to_calendar_event_minimal(mock_config_entry_with_events) -> None:
    """Test converting minimal event data to CalendarEvent."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    test_date = datetime.now() + timedelta(days=30)
    event_data = {
        "event_date": test_date.strftime("%Y-%m-%d"),
        "musicbrainz_id": "test-id",
    }

    calendar_event = calendar_entity._convert_to_calendar_event(event_data)

    assert calendar_event is not None
    expected_date = test_date.date()
    assert calendar_event.start == expected_date
    assert calendar_event.end == expected_date + timedelta(
        days=1
    )  # Exclusive end date for all-day events
    assert calendar_event.summary == "Concert"  # Default when no text
    assert (
        calendar_event.description == "Concert by Unknown Artist"
    )  # Default performer
    assert calendar_event.location is None
    expected_uid = f"music_favorites_test-id_{test_date.strftime('%Y-%m-%d')}"
    assert calendar_event.uid == expected_uid


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
    """Test event property returns next upcoming event from cache."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Mock dt_util.now() to return a time before all events
    fixed_now = datetime.now(dt_util.UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    with patch(
        "homeassistant.components.music_favorites.calendar.dt_util.now",
        return_value=fixed_now,
    ):
        next_event = calendar_entity.event

    assert next_event is not None
    # Should return the earliest event from cache (first processed event)
    earliest_date_str = mock_config_entry_with_events.runtime_data[
        "filtered_calendar_events"
    ][0]["event_date"]
    earliest_date = datetime.strptime(earliest_date_str, "%Y-%m-%d").date()
    assert next_event.start == earliest_date
    assert next_event.summary is not None
    event_name = str(VULVODYNIA_EVENTS_LDJSON[0]["name"])
    assert event_name in next_event.summary


def test_event_property_no_upcoming_events(mock_config_entry_with_events) -> None:
    """Test event property returns None when no upcoming events in cache."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Mock dt_util.now() to return a time after all events
    fixed_now = datetime.now(dt_util.UTC) + timedelta(days=365)
    with patch(
        "homeassistant.components.music_favorites.calendar.dt_util.now",
        return_value=fixed_now,
    ):
        next_event = calendar_entity.event

    assert next_event is None


def test_event_property_empty_favorites() -> None:
    """Test event property with empty cache."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"favorites": {}, "distance_filter": 100},
        unique_id="music_favorites",
    )
    mock_entry.runtime_data = {"filtered_calendar_events": []}

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
    """Test getting events within a date range from cache."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Get events for a range that covers all cached events (dynamic dates)
    cached_events = mock_config_entry_with_events.runtime_data[
        "filtered_calendar_events"
    ]
    first_event_date = datetime.strptime(cached_events[0]["event_date"], "%Y-%m-%d")
    last_event_date = datetime.strptime(cached_events[-1]["event_date"], "%Y-%m-%d")
    start_date = first_event_date.replace(day=1, tzinfo=dt_util.UTC)
    end_date = (last_event_date + timedelta(days=5)).replace(
        tzinfo=dt_util.UTC
    )  # Beyond last event

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    # Should return 2 events (both Vulvodynia events from cache)
    assert len(events) == 2
    # Verify events match cached data (dynamic dates)
    expected_date_1 = datetime.strptime(
        cached_events[0]["event_date"], "%Y-%m-%d"
    ).date()
    expected_date_2 = datetime.strptime(
        cached_events[1]["event_date"], "%Y-%m-%d"
    ).date()
    assert events[0].start == expected_date_1
    assert events[1].start == expected_date_2

    # Events should be sorted by start time
    assert events[0].start <= events[1].start


async def test_async_get_events_no_overlap(
    hass: HomeAssistant, mock_config_entry_with_events
) -> None:
    """Test getting events with no date range overlap from cache."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Get events for a time period with no events in cache (past dates)
    past_start = datetime.now(dt_util.UTC) - timedelta(days=60)
    past_end = datetime.now(dt_util.UTC) - timedelta(days=30)
    start_date = past_start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = past_end.replace(hour=23, minute=59, second=59, microsecond=0)

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    assert len(events) == 0


async def test_async_get_events_invalid_event_data(hass: HomeAssistant) -> None:
    """Test getting events when cache contains some invalid data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "events": [
                        {
                            "text": "Valid Event",
                            "event_date": (
                                datetime.now() + timedelta(days=30)
                            ).strftime("%Y-%m-%d"),
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
            },
            "distance_filter": 100,
        },
        unique_id="music_favorites",
    )
    # Cache contains only valid events (invalid ones filtered out during cache creation)
    mock_entry.runtime_data = {
        "filtered_calendar_events": [
            {
                "text": "Valid Event",
                "event_date": (datetime.now() + timedelta(days=30)).strftime(
                    "%Y-%m-%d"
                ),
                "performer_name": "Test Artist",
                "musicbrainz_id": "artist-id",
            }
        ]
    }

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    # Use dynamic dates that will cover the test event
    test_event_date = datetime.now() + timedelta(days=30)
    start_date = test_event_date.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=dt_util.UTC
    )
    end_date = (test_event_date + timedelta(days=32)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=dt_util.UTC
    )

    events = await calendar_entity.async_get_events(hass, start_date, end_date)

    # Should only return the valid event from cache
    assert len(events) == 1
    assert events[0].summary == "Valid Event"


def test_extra_state_attributes(mock_config_entry_with_events) -> None:
    """Test extra state attributes property."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    attrs = calendar_entity.extra_state_attributes
    assert attrs is not None
    assert "next_shows" in attrs
    assert isinstance(attrs["next_shows"], str)


def test_generate_next_shows_text_with_events() -> None:
    """Test generating next shows text with upcoming events."""
    # Create future events that will always be upcoming
    future_date_1 = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    future_date_2 = (datetime.now() + timedelta(days=35)).strftime("%Y-%m-%d")

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    "events": [
                        {
                            "event_date": future_date_1,
                            "text": "Concert 1",
                            "location": "Venue 1",
                            "venue_time_display": "8:00 PM",
                        },
                        {
                            "event_date": future_date_2,
                            "text": "Concert 2",
                            "location": "Venue 2",
                            "venue_time_display": "7:30 PM",
                        },
                    ],
                }
            }
        },
        unique_id="music_favorites",
    )
    # Set up runtime_data with cache that calendar entity expects
    mock_entry.runtime_data = {
        "filtered_calendar_events": [
            {
                "event_date": future_date_1,
                "text": "Concert 1",
                "location": "Venue 1",
                "venue_time_display": "8:00 PM",
                "performer_name": "Test Artist",
                "musicbrainz_id": "artist-id",
            },
            {
                "event_date": future_date_2,
                "text": "Concert 2",
                "location": "Venue 2",
                "venue_time_display": "7:30 PM",
                "performer_name": "Test Artist",
                "musicbrainz_id": "artist-id",
            },
        ]
    }

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    next_shows_text = calendar_entity._generate_next_shows_text()

    assert "No upcoming shows found" not in next_shows_text
    assert "Test Artist" in next_shows_text
    assert "Venue 1" in next_shows_text
    assert "Venue 2" in next_shows_text
    assert " // " in next_shows_text  # Separator between events


def test_generate_next_shows_text_no_upcoming_events(
    mock_config_entry_with_events,
) -> None:
    """Test generating next shows text with no upcoming events."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_config_entry_with_events.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_config_entry_with_events, device_info)

    # Mock dt_util.now() to return a time after all events
    fixed_now = datetime.now(dt_util.UTC) + timedelta(days=365)
    with patch(
        "homeassistant.components.music_favorites.calendar.dt_util.now",
        return_value=fixed_now,
    ):
        next_shows_text = calendar_entity._generate_next_shows_text()

    assert next_shows_text == "No upcoming shows found"


def test_generate_next_shows_text_empty_favorites() -> None:
    """Test generating next shows text with empty favorites."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"favorites": {}},
        unique_id="music_favorites",
    )
    mock_entry.runtime_data = {"filtered_calendar_events": []}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    next_shows_text = calendar_entity._generate_next_shows_text()
    assert next_shows_text == "No upcoming shows found"


def test_generate_next_shows_text_limits_to_10_events() -> None:
    """Test that next shows text is limited to 10 events."""
    # Create 15 future events to test the limit
    base_date = datetime.now() + timedelta(days=10)
    events = []
    for i in range(15):
        event_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        events.append(
            {
                "event_date": event_date,
                "text": f"Event {i + 1}",
                "location": f"Venue {i + 1}",
            }
        )

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    "events": events,
                }
            }
        },
        unique_id="music_favorites",
    )
    # Set up runtime_data with cache that calendar entity expects
    cached_events = []
    for i in range(15):
        event_date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        cached_events.append(
            {
                "event_date": event_date,
                "text": f"Event {i + 1}",
                "location": f"Venue {i + 1}",
                "performer_name": "Test Artist",
                "musicbrainz_id": "artist-id",
            }
        )
    mock_entry.runtime_data = {"filtered_calendar_events": cached_events}

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    next_shows_text = calendar_entity._generate_next_shows_text()

    # Count events in the text (should be limited to 10)
    event_count = (
        next_shows_text.count(" // ") + 1
        if "No upcoming shows found" not in next_shows_text
        else 0
    )
    assert event_count == 10

    # Verify it contains the first 10 events
    assert "1. Test Artist @ Venue 1" in next_shows_text
    assert "10. Test Artist @ Venue 10" in next_shows_text
    # But not the 11th event
    assert "11. Test Artist @ Venue 11" not in next_shows_text


def test_generate_next_shows_text_invalid_date_format() -> None:
    """Test generating next shows text with invalid event dates."""
    # Use a future date that will always be upcoming
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "favorites": {
                "artist-id": {
                    "variants": ["Test Artist"],
                    "status": "Active",
                    "events": [
                        {
                            "event_date": future_date,  # Valid future date
                            "text": "Valid Event",
                            "location": "Valid Venue",
                        },
                        {
                            "event_date": "invalid-date",  # Invalid
                            "text": "Invalid Event",
                            "location": "Invalid Venue",
                        },
                        {
                            # No event_date
                            "text": "No Date Event",
                            "location": "No Date Venue",
                        },
                    ],
                }
            }
        },
        unique_id="music_favorites",
    )
    # Cache contains only valid events (invalid ones filtered out during cache creation)
    mock_entry.runtime_data = {
        "filtered_calendar_events": [
            {
                "event_date": future_date,
                "text": "Valid Event",
                "location": "Valid Venue",
                "performer_name": "Test Artist",
                "musicbrainz_id": "artist-id",
            }
        ]
    }

    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{mock_entry.entry_id}_calendar")},
        name="Concert Calendar",
    )

    calendar_entity = MusicFavoritesCalendar(mock_entry, device_info)

    next_shows_text = calendar_entity._generate_next_shows_text()

    # Should only contain the valid event from cache
    assert "Valid Venue" in next_shows_text
    assert "Invalid Venue" not in next_shows_text
    assert "No Date Venue" not in next_shows_text


def test_format_event_for_text_complete() -> None:
    """Test formatting event for text with complete data."""
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

    # Use a future date for the test
    test_date = datetime.now() + timedelta(days=30)
    event_data = {
        "performer_name": "Test Artist",
        "location": "Test Venue",
        "event_date": test_date.strftime("%Y-%m-%d"),
        "venue_time_display": "8:00 PM",
    }

    formatted_event = calendar_entity._format_event_for_text(event_data)

    expected = f"Test Artist @ Test Venue - {test_date.strftime('%b %d, %Y')} 8:00 PM"
    assert formatted_event == expected


def test_format_event_for_text_minimal() -> None:
    """Test formatting event for text with minimal data."""
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

    # Use a future date for the test
    test_date = datetime.now() + timedelta(days=30)
    event_data = {
        "event_date": test_date.strftime("%Y-%m-%d"),
    }

    formatted_event = calendar_entity._format_event_for_text(event_data)

    expected = f"Unknown Artist @ Unknown Venue - {test_date.strftime('%b %d, %Y')}"
    assert formatted_event == expected


def test_format_event_for_text_no_time() -> None:
    """Test formatting event for text without venue time."""
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

    # Use a future date for the test
    test_date = datetime.now() + timedelta(days=30)
    event_data = {
        "performer_name": "Test Artist",
        "location": "Test Venue",
        "event_date": test_date.strftime("%Y-%m-%d"),
        # No venue_time_display
    }

    formatted_event = calendar_entity._format_event_for_text(event_data)

    expected = f"Test Artist @ Test Venue - {test_date.strftime('%b %d, %Y')}"
    assert formatted_event == expected


def test_format_event_for_text_no_event_date() -> None:
    """Test formatting event for text without event date returns None."""
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

    event_data = {
        "performer_name": "Test Artist",
        "location": "Test Venue",
        # No event_date
    }

    formatted_event = calendar_entity._format_event_for_text(event_data)

    assert formatted_event is None


def test_format_event_for_text_invalid_date() -> None:
    """Test formatting event for text with invalid date format."""
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

    event_data = {
        "performer_name": "Test Artist",
        "location": "Test Venue",
        "event_date": "invalid-date",
    }

    with patch(
        "homeassistant.components.music_favorites.calendar._LOGGER"
    ) as mock_logger:
        formatted_event = calendar_entity._format_event_for_text(event_data)

        assert formatted_event is None
        mock_logger.error.assert_called_once()
        assert "Failed to format event for text display" in str(
            mock_logger.error.call_args
        )


async def test_async_will_remove_from_hass() -> None:
    """Test async_will_remove_from_hass method."""
    entry = MockConfigEntry(domain=DOMAIN, data={"favorites": {}})
    entry.runtime_data = {
        "filtered_calendar_events": [],
        "calendar_entity": "test_entity",
    }
    device_info = DeviceInfo(identifiers={(DOMAIN, "test")}, name="Test")
    calendar_entity = MusicFavoritesCalendar(entry, device_info)

    # Mock the super method
    with patch(
        "homeassistant.components.calendar.CalendarEntity.async_will_remove_from_hass"
    ) as mock_super:
        await calendar_entity.async_will_remove_from_hass()

    # Verify calendar entity was removed from runtime_data
    assert "calendar_entity" not in entry.runtime_data
    # Verify super method was called
    mock_super.assert_called_once()


async def test_async_get_events_with_invalid_event_data() -> None:
    """Test async_get_events with invalid event data that can't be converted."""
    entry = MockConfigEntry(domain=DOMAIN, data={"favorites": {}})
    # Add invalid event data that will return None from _convert_to_calendar_event
    entry.runtime_data = {
        "filtered_calendar_events": [
            {"event_date": ""},  # Empty date will cause conversion to fail
            {
                "performer_name": "Valid Artist",
                "event_date": "2025-12-01",
            },  # Valid event
        ]
    }
    device_info = DeviceInfo(identifiers={(DOMAIN, "test")}, name="Test")
    calendar_entity = MusicFavoritesCalendar(entry, device_info)

    start_date = dt_util.as_utc(datetime(2025, 12, 1))
    end_date = dt_util.as_utc(datetime(2025, 12, 2))

    # Run the async method
    events = await calendar_entity.async_get_events(None, start_date, end_date)

    # Should only have one event (the valid one), invalid event should be skipped
    assert len(events) == 1
    assert events[0].summary == "Concert"


def test_generate_next_shows_text_with_missing_event_dates() -> None:
    """Test _generate_next_shows_text with events missing event_date."""
    entry = MockConfigEntry(domain=DOMAIN, data={"favorites": {}})
    entry.runtime_data = {
        "filtered_calendar_events": [
            {"performer_name": "Artist 1"},  # Missing event_date
            {"performer_name": "Artist 2", "event_date": ""},  # Empty event_date
            {
                "performer_name": "Artist 3",
                "event_date": "2025-12-01",
                "location": "Venue 3",
            },  # Valid
        ]
    }
    device_info = DeviceInfo(identifiers={(DOMAIN, "test")}, name="Test")
    calendar_entity = MusicFavoritesCalendar(entry, device_info)

    result = calendar_entity._generate_next_shows_text()

    # Should only include the valid event
    assert "Artist 3" in result
    assert "Artist 1" not in result
    assert "Artist 2" not in result


def test_generate_next_shows_text_with_date_parsing_errors() -> None:
    """Test _generate_next_shows_text with date parsing errors."""
    entry = MockConfigEntry(domain=DOMAIN, data={"favorites": {}})
    entry.runtime_data = {
        "filtered_calendar_events": [
            {
                "performer_name": "Artist 1",
                "event_date": "invalid-date",
            },  # Invalid date format
            {"performer_name": "Artist 2", "event_date": 12345},  # Wrong type
            {
                "performer_name": "Artist 3",
                "event_date": "2025-12-01",
                "location": "Venue 3",
            },  # Valid
        ]
    }
    device_info = DeviceInfo(identifiers={(DOMAIN, "test")}, name="Test")
    calendar_entity = MusicFavoritesCalendar(entry, device_info)

    with patch(
        "homeassistant.components.music_favorites.calendar._LOGGER"
    ) as mock_logger:
        result = calendar_entity._generate_next_shows_text()

    # Should only include the valid event
    assert "Artist 3" in result
    assert "Artist 1" not in result
    assert "Artist 2" not in result
    # Should log warnings for parsing errors
    mock_logger.warning.assert_called()
    assert "Failed to parse event date" in str(mock_logger.warning.call_args)
