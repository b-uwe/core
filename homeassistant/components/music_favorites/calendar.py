"""Calendar platform for the Music Favorites integration."""

from __future__ import annotations

from collections.abc import Mapping
import datetime
import logging
import re
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .calendar_utils import create_calendar_device_info
from .datatypes import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)

# That's kinda bullshit because the calendar doesn't fetch anything. But... 🤷
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up calendar platform from config entry with distance-filtered event display.

    Creates a single calendar entity that displays upcoming concert events from all
    favorite artists, filtered by distance from the Home Assistant location. This
    calendar integrates with the broader synchronization system to show events
    automatically updated by the coordinator.

    Calendar Platform Setup:
    1. Create shared device info → Groups calendar with select entities under "Settings" device
    2. Create calendar entity → Single entity showing all filtered events
    3. Register entity → Entity appears in UI immediately and connects to sync system

    Event Data Source:
    - Uses entry.runtime_data["filtered_calendar_events"] → A pre-filtered events cache
    - Cache updated by coordinator → New events appear automatically and heavy operations happen
      on (much more rare) write, not on read
    - Distance filtering applied → Only events within user-configured distance shown

    Args:
        hass: Home Assistant instance for entity registration and location access
        entry: Config entry containing calendar cache and serving as central data store
        async_add_entities: HA callback to register calendar entity and trigger UI appearance

    Returns:
        None

    Side Effects:
        - Creates calendar entity → Entity appears in calendar integrations immediately
        - Entity registers config listeners → Automatic sync when coordinator updates cache
        - Sets up device grouping → Calendar grouped with distance filter select entity
    """
    _LOGGER.debug("Setting up Music Favorites calendar entity")

    # Create device info for calendar (shared with select entities)
    device_info = create_calendar_device_info(entry.entry_id)

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
        """Initialize calendar entity with config entry connection and device grouping.

        Sets up the calendar entity that displays distance-filtered concert events
        from all favorite artists. The calendar reads from pre-filtered event cache
        and automatically synchronizes with coordinator updates.

        Entity Configuration:
        - Name: "Concert Calendar" → User-friendly calendar name in UI
        - Unique ID: Based on config entry → Survives restarts and reloads
        - Device grouping → Groups with distance filter select under "Settings" device

        Data Source Setup:
        - Stores config entry reference → Used to access filtered event cache
        - Event cache in entry.runtime_data → Updated by coordinator and calendar utils
        - No direct API calls → Calendar reads from pre-processed, filtered data for speed
          reasons

        Args:
            entry: Config entry containing event cache and serving as data source
            device_info: Shared device info for grouping with related settings entities

        Returns:
            None

        Side Effects:
            - Sets entity name and unique ID → Entity appears with proper identification
            - Associates with device → Groups calendar under settings device in UI
            - Stores config entry reference → Enables access to filtered event data
        """
        self._entry = entry
        self._attr_name = "Concert Calendar"
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        """Register calendar entity with Home Assistant and establish synchronization.

        This lifecycle method connects the calendar entity to the synchronization system,
        ensuring it receives updates when favorites change or events are updated by
        the coordinator.

        Synchronization Setup:
        - Registers in runtime_data → Makes calendar accessible for cache updates
        - Adds config entry listener → Calendar refreshes when coordinator updates data
        - Uses async_on_remove() → Ensures cleanup when entity removed

        Runtime Data Registration:
        - Stores self in entry.runtime_data → Used by calendar_utils for cache updates
        - Enables direct calendar refresh → When distance filter changes or new events added

        Args:
            None

        Returns:
            None

        Side Effects:
            - Registers in runtime_data → Calendar becomes accessible for external updates
            - Sets up config entry listener → Automatic refresh when data changes
            - Establishes cleanup callback → Listener removed when entity unloaded
        """
        await super().async_added_to_hass()

        # Register this calendar entity in runtime_data for easy access
        self._entry.runtime_data["calendar_entity"] = self

        # Register listener for config entry updates and ensure cleanup when entity is removed
        self.async_on_remove(
            self._entry.add_update_listener(self._config_entry_updated)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up calendar entity resources before removal from Home Assistant.

        This lifecycle method ensures proper cleanup when the calendar entity is
        being removed, preventing memory leaks and orphaned references.

        Cleanup Operations:
        - Removes self from runtime_data → Prevents access to removed entity
        - Calls parent cleanup → HA handles config entry listener cleanup automatically

        Args:
            None

        Returns:
            None

        Side Effects:
            - Removes calendar_entity from runtime_data → calendar_utils can no longer access
            - Parent cleanup called → Config entry listeners automatically cleaned up
        """
        # Unregister calendar entity from runtime_data
        self._entry.runtime_data.pop("calendar_entity", None)
        await super().async_will_remove_from_hass()

    async def _config_entry_updated(
        self, hass: HomeAssistant, entry: MusicFavoritesConfigEntry
    ) -> None:
        """Handle config entry updates and trigger calendar UI refresh.

        This callback is triggered whenever the config entry data changes, ensuring
        the calendar entity immediately reflects updated event information in the UI.

        Trigger Sources:
        - Coordinator updates → New events fetched from APIs
        - Favorite changes → add_favorite/remove_favorite service calls
        - Distance filter changes → User modifies distance setting via select entity
        - Calendar cache updates → calendar_utils refreshes filtered events

        UI Update Process:
        1. Config entry updated → This callback triggered immediately
        2. async_write_ha_state() → Queues calendar refresh on next event loop
        3. Calendar properties re-evaluated → event, async_get_events, extra_state_attributes
        4. UI updates → Calendar shows new events, entity state refreshes

        Args:
            hass: Home Assistant instance (required by HA callback signature)
            entry: Updated config entry with fresh calendar cache data

        Returns:
            None

        Side Effects:
            - Schedules UI state update → Calendar refreshes in UI
            - Triggers property re-evaluation → Calendar reads fresh filtered events
        """
        _LOGGER.debug("Config entry updated, refreshing calendar entity")
        self.async_write_ha_state()

    def _get_all_events(self) -> list[dict[str, Any]]:
        """Get all filtered events from runtime_data cache.

        Returns:
            List of raw event dictionaries, pre-filtered by distance
        """
        # Return the pre-filtered events from cache
        cached_events = self._entry.runtime_data.get("filtered_calendar_events", [])
        return cached_events if isinstance(cached_events, list) else []

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

            # Create enhanced description with time info and URL
            description_parts = [f"Concert by {performer_name}"]
            if venue_time_display:
                description_parts.append(f"Time: {venue_time_display} venue local time")

            # Add Bandsintown event URL if available
            event_url = event_data.get("url")
            if event_url:
                description_parts.append(
                    f"Event details: {re.sub(r'[?&]came_from=\d+', '', event_url)}"
                )

            # The lack of formatting options is REALLY annoying
            # Not having GEO data is annoying, not having URLs is annoying
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
        """Return the next upcoming event for calendar entity state display.

        This property provides the primary calendar entity state by returning the
        earliest upcoming concert event. The event appears as the calendar's current
        state in the UI and drives calendar integration displays.

        Event Selection Logic:
        - Filters all events for future dates → Only upcoming events considered
        - Converts to CalendarEvent objects → Standardized HA calendar format
        - Returns earliest upcoming event → Chronologically next concert

        UI Integration:
        - Calendar entity state → Shows next event summary and date
        - Calendar integrations → Displays next event in dashboards
        - Automatic updates → Changes when coordinator updates events or time passes

        Returns:
            CalendarEvent: Next upcoming concert event with full details
            None: No upcoming events found in filtered cache

        Data Source:
            Uses _get_all_events() → Pre-filtered events from runtime_data cache
            Events already distance-filtered → Only shows relevant nearby concerts
        """
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
        """Return concert events within specified datetime range for calendar display.

        This method is called by Home Assistant's calendar system to fetch events
        for display in calendar views, providing filtered concert events within
        the requested time window.

        Calendar Integration:
        - Called by HA calendar system → When calendar view requests events
        - Date range filtering → Only returns events within requested window
        - Sorted chronologically → Events appear in correct order in calendar

        Event Processing:
        1. Get all filtered events → From pre-distance-filtered runtime_data cache
        2. Convert to CalendarEvent → Standardized HA calendar format
        3. Filter by date range → Only events overlapping requested period
        4. Sort chronologically → Proper calendar display order

        Args:
            hass: Home Assistant instance (required by calendar interface)
            start_date: Beginning of requested time range (timezone-aware datetime)
            end_date: End of requested time range (timezone-aware datetime)

        Returns:
            list[CalendarEvent]: Sorted list of concert events within date range
                                Events are pre-filtered by distance and converted to HA format

        Data Source:
            Uses _get_all_events() → Pre-filtered, distance-limited events cache
            No additional filtering → Distance filter already applied by calendar_utils
        """
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

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional calendar entity attributes.

        We have one - with a summary of upcoming shows.

        This provides enhanced calendar entity information beyond the basic state,
        offering a quick overview of upcoming concerts in a formatted text attribute.
        The format tries to strike a balance between readability in plain text and
        identifiable parts to apply regexes to put it into a markdown card

        Attribute Content:
        - "next_shows": Formatted text listing next 10 upcoming concerts
        - Format: "1. Artist @ Venue - Date Time // 2. Artist @ Venue - Date Time..."
        - Chronologically sorted → Most immediate shows listed first

        UI Integration:
        - Entity details panel → Shows next_shows attribute in entity information
        - Dashboard use → Attribute can be displayed in template or markdown cards
        - Automatic updates → Refreshes when calendar entity state updates

        Returns:
            Mapping: Dictionary with "next_shows" key containing formatted upcoming concerts text
                    Returns summary of next 10 events or "No upcoming shows found"

        Data Source:
            Uses _generate_next_shows_text() → Processes filtered events for text display
            Same data as main calendar → Consistent with calendar entity event display
        """
        return {"next_shows": self._generate_next_shows_text()}

    def _generate_next_shows_text(self) -> str:
        """Generate formatted text summary of the next 10 upcoming concerts for entity attributes.

        Creates a compact, readable text representation of upcoming concerts that can be
        displayed in entity attributes panels and used in dashboard template cards.
        The format balances human readability with structure for regex parsing.

        Text Generation Process:
        1. Filter events for upcoming dates → Only future concerts included
        2. Sort chronologically → Most immediate shows listed first
        3. Limit to 10 events → Prevents excessively long attribute text
        4. Format with numbered list → "1. Artist @ Venue - Date Time // 2. ..."

        Format Design:
        - Numbered list → Easy identification of individual events
        - " // " separator → Clear event boundaries for regex parsing
        - "Artist @ Venue - Date Time" → Consistent, parseable structure
        - Human readable dates → "Jan 15, 2025" format for clarity

        UI Integration:
        - Entity attributes panel → Shows next_shows in entity details
        - Template cards → Can extract and format individual events
        - Dashboard displays → Quick overview of upcoming concerts

        Returns:
            Formatted text with up to 10 upcoming shows or "No upcoming shows found"
            Format: "1. Artist @ Venue - Date Time // 2. Artist @ Venue - Date Time..."

        Data Source:
            Uses _get_all_events() → Same filtered cache as main calendar display
            Consistent with calendar entity → Shows same events as calendar view
        """
        now = dt_util.now()
        upcoming_events = []

        # Get all events and filter for upcoming ones
        for event_data in self._get_all_events():
            try:
                event_date_str = event_data.get("event_date")
                if not event_date_str:
                    continue

                # Parse event date and convert to datetime for comparison
                event_date = datetime.datetime.strptime(
                    event_date_str, "%Y-%m-%d"
                ).date()
                event_datetime = datetime.datetime.combine(
                    event_date, datetime.time.min, tzinfo=now.tzinfo
                )

                if event_datetime >= now:
                    upcoming_events.append((event_datetime, event_data))

            except (ValueError, TypeError) as err:
                _LOGGER.warning("Failed to parse event date: %s", err)
                continue

        if not upcoming_events:
            return "No upcoming shows found"

        # Sort by date and take first 10
        upcoming_events.sort(key=lambda x: x[0])
        next_10_events = upcoming_events[:10]

        # Format the text
        text_lines = []
        for i, (_, event_data) in enumerate(next_10_events, 1):
            formatted_event = self._format_event_for_text(event_data)
            if formatted_event:
                text_lines.append(f"{i}. {formatted_event}")

        return " // ".join(text_lines) if text_lines else "No upcoming shows found"

    def _format_event_for_text(self, event_data: dict[str, Any]) -> str | None:
        """Format a single concert event into structured text for readable display.

        Converts raw event data into a standardized, human-readable string format that
        maintains consistent structure for both display and potential regex parsing.
        Used by _generate_next_shows_text() to create the entity attributes summary.

        Format Structure:
        - Pattern: "Artist @ Venue - Date Time"

        Error Handling:
        - Missing event_date → Returns None (event skipped)
        - Invalid date format → Logs error and returns None
        - Missing other fields → Uses fallback values ("Unknown Artist", "Unknown Venue")

        Args:
            event_data: Raw event dictionary with performer_name, location, event_date, venue_time_display

        Returns:
            str: Formatted event string "Artist @ Venue - Date Time" for display
            None: Formatting failed due to missing/invalid date data

        Side Effects:
            - Logs formatting errors → Debugging for invalid event data
            - No state changes → Pure formatting function
        """
        try:
            performer_name = event_data.get("performer_name", "Unknown Artist")
            venue_name = event_data.get("location", "Unknown Venue")
            event_date_str = event_data.get("event_date")
            venue_time_display = event_data.get("venue_time_display", "")

            if not event_date_str:
                return None

            # Parse event date
            event_date = datetime.datetime.strptime(event_date_str, "%Y-%m-%d").date()

        except (ValueError, TypeError) as err:
            _LOGGER.error("Failed to format event for text display: %s", err)
            return None
        else:
            date_formatted = event_date.strftime("%b %d, %Y")

            # Create formatted string: "Artist @ Venue - Date Time"
            time_part = f" {venue_time_display}" if venue_time_display else ""
            return f"{performer_name} @ {venue_name} - {date_formatted}{time_part}"
