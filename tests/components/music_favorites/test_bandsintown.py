"""Tests for the bandsintown module."""

from homeassistant.components.music_favorites.bandsintown import extract_music_events

from .fixtures.bandsintown_responses import (
    MIXED_LDJSON_DATA,
    VULVODYNIA_BAND_LDJSON,
    VULVODYNIA_EVENTS_LDJSON,
)


def test_extract_music_events_real_data() -> None:
    """Test extract_music_events with real Vulvodynia events from Bandsintown."""
    result = extract_music_events(VULVODYNIA_EVENTS_LDJSON)

    assert len(result) == 2

    # Test first event (O2 Academy Islington)
    event1 = result[0]
    assert event1["text"] == "Vulvodynia @ O2 Academy Islington"
    assert event1["start_date"] == "2025-11-25T18:00:00"
    assert event1["end_date"] == "2025-11-25"
    assert (
        event1["url"]
        == "https://www.bandsintown.com/e/1036117971-vulvodynia-at-o2-academy-islington?came_from=209"
    )
    assert event1["location"] == "O2 Academy Islington"
    assert (
        event1["venue_address"] == "N1 Centre 16 Parkfield St, London, United Kingdom"
    )
    assert event1["performer"] == "Vulvodynia"
    assert event1["latitude"] == 51.5343501
    assert event1["longitude"] == -0.1058837

    # Test second event (Leeds University Stylus)
    event2 = result[1]
    assert event2["text"] == "Vulvodynia @ Leeds University Stylus"
    assert event2["start_date"] == "2025-11-28T17:30:00"
    assert event2["end_date"] == "2025-11-28"
    assert (
        event2["url"]
        == "https://www.bandsintown.com/e/1035095196-vulvodynia-at-leeds-university-stylus?came_from=209"
    )
    assert event2["location"] == "Leeds University Stylus"
    assert (
        event2["venue_address"]
        == "Leeds University Union,, Lifton Pl, Leeds, United Kingdom"
    )
    assert event2["performer"] == "Vulvodynia"
    assert event2["latitude"] == 53.79648
    assert event2["longitude"] == -1.54785


def test_extract_music_events_mixed_data() -> None:
    """Test extract_music_events with mixed LD+JSON data (events and non-events)."""
    result = extract_music_events(MIXED_LDJSON_DATA)

    # Should only extract the 2 MusicEvent objects, ignoring MusicGroup and Review
    assert len(result) == 2
    assert result[0]["text"] == "Vulvodynia @ O2 Academy Islington"
    assert result[1]["text"] == "Vulvodynia @ Leeds University Stylus"


def test_extract_music_events_no_music_events() -> None:
    """Test extract_music_events with no MusicEvent objects."""
    non_event_data = [VULVODYNIA_BAND_LDJSON]
    result = extract_music_events(non_event_data)
    assert result == []


def test_extract_music_events_empty_data() -> None:
    """Test extract_music_events with empty data."""
    result = extract_music_events([])
    assert result == []


def test_extract_music_events_minimal_event() -> None:
    """Test extract_music_events with minimal event data."""
    minimal_event = [{"@type": "MusicEvent", "name": "Test Event"}]

    result = extract_music_events(minimal_event)

    assert len(result) == 1
    event = result[0]
    assert event["text"] == "Test Event"
    assert event["start_date"] is None
    assert event["end_date"] is None
    assert event["url"] is None
    assert event["location"] is None
    assert event["venue_address"] is None
    assert event["performer"] is None
    assert event["latitude"] is None
    assert event["longitude"] is None


def test_extract_music_events_missing_name() -> None:
    """Test extract_music_events with missing event name."""
    event_no_name = [{"@type": "MusicEvent", "startDate": "2025-01-01"}]

    result = extract_music_events(event_no_name)

    assert len(result) == 1
    event = result[0]
    assert event["text"] == "Unknown Event"
    assert event["start_date"] == "2025-01-01"


def test_extract_music_events_partial_address() -> None:
    """Test extract_music_events with partial address information."""
    event_partial_address = [
        {
            "@type": "MusicEvent",
            "name": "Test Event",
            "location": {
                "@type": "Place",
                "name": "Test Venue",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Test City",
                    "addressCountry": "Test Country",
                    # Missing streetAddress
                },
            },
        }
    ]

    result = extract_music_events(event_partial_address)

    assert len(result) == 1
    event = result[0]
    assert event["location"] == "Test Venue"
    assert event["venue_address"] == "Test City, Test Country"
    assert event["latitude"] is None
    assert event["longitude"] is None


def test_extract_music_events_no_geolocation() -> None:
    """Test extract_music_events with location but no geo coordinates."""
    event_no_geo = [
        {
            "@type": "MusicEvent",
            "name": "Test Event",
            "location": {
                "@type": "Place",
                "name": "Test Venue",
                "address": {"@type": "PostalAddress", "streetAddress": "123 Test St"},
                # No geo field
            },
        }
    ]

    result = extract_music_events(event_no_geo)

    assert len(result) == 1
    event = result[0]
    assert event["venue_address"] == "123 Test St"
    assert event["latitude"] is None
    assert event["longitude"] is None
