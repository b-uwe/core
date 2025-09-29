"""Calendar platform for the Music Favorites integration."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION
from .datatypes import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)

# That's kinda bullshit because the calendar doesn't fetch anything. But...
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites calendar from a config entry."""
    _LOGGER.debug("Setting up Music Favorites calendar entity")

    # Create device info for calendar (separate from acts device)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_calendar")},
        name="Concert Calendar",
        manufacturer="Music Favorites Integration",
        model="Event Calendar",
        sw_version=VERSION,
        configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
    )

    # Create the calendar entity
    calendar_entity = MusicFavoritesCalendar(entry, device_info)
    async_add_entities([calendar_entity])

    _LOGGER.debug("Music Favorites calendar entity created")


class MusicFavoritesCalendar(CalendarEntity):
    """Calendar entity for Music Favorites concerts and events."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MusicFavoritesConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the calendar entity."""
        self._entry = entry
        self._attr_name = "Concert Calendar"
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        await super().async_added_to_hass()

        # Listen for config entry updates to refresh calendar when favorites change
        self.async_on_remove(
            self._entry.add_update_listener(self._config_entry_updated)
        )

    async def _config_entry_updated(
        self, hass: HomeAssistant, entry: MusicFavoritesConfigEntry
    ) -> None:
        """Handle config entry update."""
        _LOGGER.debug("Config entry updated, refreshing calendar entity")
        self.async_write_ha_state()

    def _get_all_events(self) -> list[dict[str, Any]]:
        """Get all events from all favorite acts.

        Returns:
            List of raw event dictionaries from Bandsintown data
        """
        all_events = []
        favorites_data = self._entry.data.get("favorites", {})

        for musicbrainz_id, favorite_data in favorites_data.items():
            events_data = favorite_data.get("events", [])
            variants = favorite_data.get("variants", [])
            performer_name = variants[0] if variants else "Unknown Artist"

            # Add performer info to each event for calendar display
            for event in events_data:
                event_with_performer = event.copy()
                event_with_performer["performer_name"] = performer_name
                event_with_performer["musicbrainz_id"] = musicbrainz_id
                all_events.append(event_with_performer)
        return all_events

    def _convert_to_calendar_event(
        self, event_data: dict[str, Any]
    ) -> CalendarEvent | None:
        """Convert event data to CalendarEvent.

        Creates full-day calendar events using date objects, with venue time
        information preserved in the description.

        Args:
            event_data: Event data with pure date/time components

        Returns:
            CalendarEvent object or None if conversion fails
        """
        try:
            # Get date from pure data format
            event_date_str = event_data.get("event_date")
            if not event_date_str:
                return None

            # Parse event date - simple date format: "2025-11-25"
            event_date = datetime.datetime.strptime(event_date_str, "%Y-%m-%d").date()

            # Get venue time for description
            venue_time_display = event_data.get("venue_time_display")

            # Create event details
            performer_name = event_data.get("performer_name", "Unknown Artist")
            event_title = event_data.get("text", "Concert")
            venue_name = event_data.get("location")
            venue_address = event_data.get("venue_address")

            # Create summary - use event_title directly (e.g., "Vulvodynia @ O2 Academy Islington")
            summary = event_title

            # Create enhanced description with time info
            description_parts = [f"Concert by {performer_name}"]
            if venue_time_display:
                description_parts.append(f"Time: {venue_time_display} venue local time")
            description = " • ".join(description_parts)

            # Create location string
            location_parts = []
            if venue_name:
                location_parts.append(venue_name)
            if venue_address:
                location_parts.append(venue_address)
            location = ", ".join(location_parts) if location_parts else None

            # Create full-day calendar event using date objects
            return CalendarEvent(
                start=event_date,  # Date object - no timezone issues!
                end=event_date,  # Same date for single-day events
                summary=summary,
                description=description,
                location=location,
                uid=f"music_favorites_{event_data.get('musicbrainz_id')}_{event_date_str}",
            )

        except (ValueError, TypeError) as err:
            _LOGGER.warning("Failed to convert event to calendar event: %s", err)
            return None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()  # Use timezone-aware now() instead of naive datetime.now()
        upcoming_events = []

        # Get all events and convert to CalendarEvent objects
        for event_data in self._get_all_events():
            calendar_event = self._convert_to_calendar_event(event_data)
            if calendar_event and calendar_event.start_datetime_local >= now:
                upcoming_events.append(calendar_event)

        if not upcoming_events:
            return None

        # Return the earliest upcoming event
        return min(upcoming_events, key=lambda e: e.start_datetime_local)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        _LOGGER.debug("Getting calendar events from %s to %s", start_date, end_date)

        calendar_events = []

        # Get all events and convert to CalendarEvent objects
        for event_data in self._get_all_events():
            calendar_event = self._convert_to_calendar_event(event_data)
            if not calendar_event:
                continue

            # Check if event falls within the requested date range
            event_start = calendar_event.start_datetime_local
            event_end = calendar_event.end_datetime_local

            # Include event if it overlaps with the requested range
            if event_end >= start_date and event_start < end_date:
                calendar_events.append(calendar_event)

        # Sort events by start time
        calendar_events.sort(key=lambda e: e.start_datetime_local)

        _LOGGER.debug(
            "Returning %d calendar events in date range", len(calendar_events)
        )

        return calendar_events
