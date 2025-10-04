"""Data models for the Music Favorites integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .bandsintown import extract_music_events
from .calendar_utils import update_filtered_calendar_cache
from .ldjson import LdJsonError, fetch_and_extract_ldjson
from .musicbrainz import MusicBrainzClient, MusicBrainzError, extract_relation_links

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class BandStatus(StrEnum):
    """Band status enumeration."""

    ACTIVE = "Active"
    DISBANDED = "Disbanded"
    ON_TOUR = "On Tour"
    REFORMED = "Reformed"
    TOUR_PLANNED = "Tour Planned"
    UNKNOWN = "Unknown"


# Status icons mapping for dynamic UI display based on band activity level
BAND_STATUS_ICONS = {
    BandStatus.ACTIVE: "mdi:guitar-electric",
    BandStatus.DISBANDED: "mdi:music-off",
    BandStatus.ON_TOUR: "mdi:bus-marker",
    BandStatus.REFORMED: "mdi:set-none",
    BandStatus.TOUR_PLANNED: "mdi:bus-clock",
    BandStatus.UNKNOWN: "mdi:help-circle",
}

# Tour-related business logic constants
REFORMED_DISPLAY_PERIOD = timedelta(days=180)  # 6 months for showing Reformed status
TOUR_GRACE_PERIOD = timedelta(days=2)  # Show "On Tour" 2 days after last event
TOUR_PLANNED_PERIOD = timedelta(days=180)
TOUR_PREVIEW_PERIOD = timedelta(days=30)  # Show "On Tour" 30 days before


def extract_pure_event_data(
    events_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract pure date and time data from Bandsintown events.

    Converts Bandsintown datetime strings into separated date and time components
    for clean, source-agnostic storage. This approach supports multiple event
    sources and eliminates timezone complexity.

    Args:
        events_data: List of event dictionaries from Bandsintown

    Returns:
        List of event dictionaries with pure date/time data
    """
    converted_events = []

    for event in events_data:
        converted_event = event.copy()

        # Extract start_date if present
        start_date_str = event.get("start_date")
        if start_date_str and len(start_date_str) == 19 and "T" in start_date_str:
            try:
                # Parse naive datetime from Bandsintown (venue local time)
                naive_start = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M:%S")
                # Store pure date and time components
                converted_event["event_date"] = naive_start.strftime("%Y-%m-%d")
                converted_event["venue_time"] = naive_start.strftime("%H:%M:%S")
                converted_event["venue_time_display"] = naive_start.strftime(
                    "%-I:%M %p"
                )
                # Remove original datetime field
                del converted_event["start_date"]
            except ValueError:
                # Keep original datetime string if parsing fails (malformed Bandsintown data)
                # This ensures we don't lose event data due to unexpected datetime formats
                pass

        # Handle end_date if present (usually just date for Bandsintown)
        end_date_str = event.get("end_date")
        if end_date_str:
            # Most Bandsintown end dates are date-only, just remove them
            # We'll use event_date for single-day events
            del converted_event["end_date"]

        converted_events.append(converted_event)

    return converted_events


def determine_band_status(
    artist_data: dict[str, Any],
    events_data: list[dict[str, Any]] | None = None,
    current_data: dict[str, Any] | None = None,
    previous_artist_data: dict[str, Any] | None = None,
) -> BandStatus:
    """Determine band status with full context for both new and existing favorites.

    This function implements the business logic for determining band status by analyzing
    MusicBrainz life-span data and upcoming events from Bandsintown. Status changes
    trigger UI updates when used by the coordinator.

    Logic Flow:
    1. Check for MusicBrainz reformation signals → REFORMED if ended=false or end date removed
    2. Maintain REFORMED status for REFORMED_DISPLAY_PERIOD → Then reassess
    3. Check MusicBrainz life-span data → DISBANDED if ended=true
    4. Analyze tour events → ON_TOUR, TOUR_PLANNED based on event dates
    5. Default to ACTIVE if none of the above apply

    Args:
        artist_data: Current artist data from MusicBrainz API containing life-span information
        events_data: Optional list of upcoming events from Bandsintown for tour status
        current_data: Optional existing favorite data for status context
        previous_artist_data: Optional previous artist data for comparing MusicBrainz changes

    Returns:
        BandStatus: Enum value representing current band status (affects UI display)

    Business Rules:
        - REFORMED: MusicBrainz signals reformation (ended=false or end date removed)
        - REFORMED (maintained): Keep for REFORMED_DISPLAY_PERIOD after initial detection
        - DISBANDED: Band has ended according to MusicBrainz (ended=true)
        - ON_TOUR: Events within 30 days before to 2 days after today
        - TOUR_PLANNED: Events within next 180 days
        - ACTIVE: Default status for active bands without tour activity
    """
    # Extract context from current data if available
    previous_status = current_data.get("status") if current_data else None
    reformed_date = current_data.get("reformed_date") if current_data else None

    today = date.today()
    current_life_span = artist_data.get("life-span", {})
    current_ended = current_life_span.get("ended", False)
    current_end_date = current_life_span.get("end")

    # Check if we should maintain REFORMED status for the display period
    if previous_status == BandStatus.REFORMED and reformed_date:
        try:
            reformed_date_obj = datetime.strptime(reformed_date, "%Y-%m-%d").date()
            if today - reformed_date_obj <= REFORMED_DISPLAY_PERIOD:
                return BandStatus.REFORMED
        except (ValueError, TypeError):
            # Invalid reformed_date, continue with normal logic
            pass

    # Check for MusicBrainz reformation signals by comparing with previous data
    if previous_artist_data:
        previous_life_span = previous_artist_data.get("life-span", {})
        previous_ended = previous_life_span.get("ended", False)
        previous_end_date = previous_life_span.get("end")

        # Reformation signal 1: ended changed from true to false
        if previous_ended and not current_ended:
            _LOGGER.info(
                "MusicBrainz reformation detected: ended changed from true to false"
            )
            return BandStatus.REFORMED

        # Reformation signal 2: end date was removed (became None)
        if previous_end_date and not current_end_date:
            _LOGGER.info(
                "MusicBrainz reformation detected: end date removed (%s -> None)",
                previous_end_date,
            )
            return BandStatus.REFORMED

    # Check if band is currently ended according to MusicBrainz
    # Either ended=true or presence of end date indicates disbanded status
    if current_ended or current_end_date:
        return BandStatus.DISBANDED

    # Band is active (not ended) - check tour status
    if events_data:
        tour_status = get_tour_status(events_data)
        if tour_status:
            return tour_status

    # Default to active
    return BandStatus.ACTIVE


async def fetch_external_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
    current_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch complete external data including artist data, relation links, events, variants and status.

    This function consolidates ALL external API data fetching into a single call,
    fetching artist data from MusicBrainz, building relation links, getting
    events from Bandsintown if available, processing artist variants/aliases, and
    determining band status.

    Args:
        hass: Home Assistant instance for API calls
        entry: Config entry containing runtime_data with shared MusicBrainz client
        musicbrainz_id: MusicBrainz artist ID to fetch data for
        current_data: Optional existing favorite data for status context (used by coordinator)

    Returns:
        dict: Complete external data with keys:
            - "artist_data": MusicBrainz artist data
            - "relation_links": Dictionary of relation URLs including musicbrainz_url
            - "events": List of events data from Bandsintown or empty list
            - "variants": List of deduplicated artist variants (name + aliases)
            - "status": Determined band status based on life-span and events

    Raises:
        MusicBrainzError: When MusicBrainz API fails
    """
    # Use shared MusicBrainz client from runtime_data
    musicbrainz_client = entry.runtime_data["musicbrainz_client"]
    artist_data = await musicbrainz_client.get_artist_by_id(musicbrainz_id)
    artist_name = artist_data["name"]

    # Extract name and aliases from MusicBrainz response (moved from add_favorite)
    aliases = [
        alias.get("name", "")
        for alias in artist_data.get("aliases", [])
        if alias.get("name")  # Only include non-empty alias names
    ]

    # Deduplicate variants using a set while preserving order (name first)
    variants_set = {artist_name}
    variants = [artist_name]

    if aliases:
        for alias in aliases:
            if alias not in variants_set:
                variants_set.add(alias)
                variants.append(alias)

    # Build relation links from artist data (merged from build_relation_links_data)
    relation_links = extract_relation_links(artist_data)
    relation_links["musicbrainz_url"] = (
        f"https://musicbrainz.org/artist/{artist_data['id']}"
    )

    # Initialize events data - will be populated from Bandsintown if available
    events_data: list[dict[str, Any]] = []

    # Extract LD+JSON data from Bandsintown URL if available
    bandsintown_url = relation_links.get("bandsintown_url")
    if bandsintown_url:
        _LOGGER.debug(
            "Found Bandsintown URL, extracting LD+JSON data: %s", bandsintown_url
        )
        try:
            # Fetching the Bandsintown page and extract the LD+JSON objects
            ldjson_data = await fetch_and_extract_ldjson(hass, bandsintown_url)

            # Parse MusicEvents
            music_events = extract_music_events(ldjson_data)
            if music_events:
                # Extract pure date and time data for storage
                events_data = extract_pure_event_data(music_events)

            _LOGGER.debug(
                "Extracted %d LD+JSON objects from Bandsintown", len(ldjson_data)
            )

        except LdJsonError as err:
            _LOGGER.warning("Failed to extract LD+JSON from Bandsintown: %s", err)
    else:
        _LOGGER.debug("No Bandsintown URL found for artist %s", artist_name)

    # Determine band status with events data and context (moved from add_favorite and coordinator)
    previous_artist_data = (
        current_data.get("previous_artist_data") if current_data else None
    )
    band_status = determine_band_status(
        artist_data, events_data, current_data, previous_artist_data
    )

    return {
        "artist_data": artist_data,
        "relation_links": relation_links,
        "events": events_data,
        "variants": variants,
        "status": band_status,
    }


def get_tour_status(events_data: list[dict[str, Any]]) -> BandStatus | None:
    """Determine current tour status based on upcoming concert event dates.

    Analyzes concert events to determine if a band is currently on tour or has
    tour plans. This function implements the business logic for tour-related
    status determination used in status icon and UI display.

    Tour Status Logic:
    - ON_TOUR: Events within 30 days before to 2 days after today
    - TOUR_PLANNED: Events within next 180 days (but not in ON_TOUR window)
    - None: No qualifying events found

    Time Windows (from const.py):
    - TOUR_PREVIEW_PERIOD: 30 days before events = "On Tour"
    - TOUR_GRACE_PERIOD: 2 days after events = still "On Tour"
    - TOUR_PLANNED_PERIOD: 180 days ahead = "Tour Planned"

    UI Impact:
    - ON_TOUR → mdi:bus-marker icon, indicates active touring
    - TOUR_PLANNED → mdi:bus-clock icon, indicates upcoming tour
    - None → Falls back to ACTIVE status with mdi:guitar-electric icon

    Args:
        events_data: List of event dicts with "event_date" keys in "YYYY-MM-DD" format

    Returns:
        BandStatus: ON_TOUR, TOUR_PLANNED, or None if no tour activity detected
                   Used by determine_band_status() for final status determination

    Business Rules:
        - ON_TOUR takes precedence over TOUR_PLANNED
        - Only parses valid date formats, skips malformed event dates
        - Uses closest future event for TOUR_PLANNED determination
    """
    today = date.today()

    # Track closest upcoming event
    closest_future_event = None
    closest_days_away = float("inf")

    for event in events_data:
        # Extract date from event (now using pure date format)
        event_date_str = event.get("event_date")
        if not event_date_str:
            continue

        try:
            # Parse event date - simple date format: "2025-11-25"
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
            days_until_event = (event_date - today).days

            # Check if currently on tour (within active window) and return
            # IMMEDIATELY, in case
            if -TOUR_GRACE_PERIOD.days <= days_until_event <= TOUR_PREVIEW_PERIOD.days:
                return BandStatus.ON_TOUR

            # Track closest future event for TOUR_PLANNED check
            if TOUR_PREVIEW_PERIOD.days < days_until_event < closest_days_away:
                closest_future_event = event_date
                closest_days_away = days_until_event

        except (ValueError, TypeError):
            # Skip events with unparsable dates
            continue

    # Check if tour is planned (future event within planning window)
    if closest_future_event and closest_days_away <= TOUR_PLANNED_PERIOD.days:
        return BandStatus.TOUR_PLANNED

    return None


async def add_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
) -> None:
    """Add a new favorite to the collection and sync across all components.

    This function performs the complete flow for adding a favorite, including
    data fetching, storage, entity creation, and cache updates.

    Data Flow & Synchronization Points:
    1. Fetch artist data from MusicBrainz API → Get name, aliases, relations
    2. Fetch events from Bandsintown → Get upcoming concerts/tour info
    3. Update config entry data → Triggers config entry listeners across platforms
    4. Create sensor entity dynamically → New entity appears in UI immediately
    5. Update calendar cache → Calendar events become available

    UI Update Points:
    - Config entry update → All platforms receive update notifications
    - Entity creation → New sensor appears in UI with current status
    - Calendar cache update → Concert events appear in calendar entity
    - Entity state refresh → Status and events display with real data

    Args:
        hass: Home Assistant instance for API calls and entity management
        entry: Config entry to store the favorite data (triggers sync to other components)
        musicbrainz_id: Unique MusicBrainz identifier for the artist

    Returns:
        None

    Raises:
        ServiceValidationError: When favorite already exists or MusicBrainz API fails

    Side Effects:
        - Modifies entry.data["favorites"] → Triggers all config entry listeners
        - Creates new sensor entity → Entity appears in UI immediately
        - Updates calendar cache → Calendar entity refreshes with new events
        - No HA events fired (events only fired during coordinator updates)
    """
    _LOGGER.debug("Adding favorite with MusicBrainz ID: %s", musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if already exists
    if musicbrainz_id in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID {musicbrainz_id} already exists"
        )

    # Fetch complete external data (artist data + relation links + events)
    try:
        external_data = await fetch_external_data(hass, entry, musicbrainz_id)
    except MusicBrainzError as err:
        _LOGGER.error("Failed to fetch artist data for %s: %s", musicbrainz_id, err)
        raise ServiceValidationError(
            f"Could not fetch artist data from MusicBrainz: {err}"
        ) from err

    # Extract data from comprehensive response
    artist_data = external_data["artist_data"]
    relation_links = external_data["relation_links"]
    events_data = external_data["events"]
    favorite_variants = external_data["variants"]  # Use processed variants
    band_status = external_data["status"]  # Use calculated status

    # Store variants, status, events, and flatten relation links directly into the data structure
    favorite_data = {
        "variants": favorite_variants,
        "status": band_status,
        "events": events_data,  # Store events data with the act
        **relation_links,  # Flatten relation links including musicbrainz_url into the object
    }
    current_favorites[musicbrainz_id] = favorite_data

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # Add the new entity dynamically using the entity manager
    # Only add entity if runtime_data exists and contains entity_manager
    # (during tests or before setup, this might not be available)
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        entity_manager = entry.runtime_data.get("entity_manager")
        if entity_manager:
            entity_manager.add_favorite_entity(musicbrainz_id, favorite_data)
        else:
            _LOGGER.warning(
                "Entity manager not found in runtime_data - new entity will not be created immediately"
            )
    else:
        _LOGGER.warning(
            "No runtime_data available - new entity will not be created immediately"
        )

    _LOGGER.info("Successfully added favorite: %s", artist_data["name"])

    # Update filtered calendar cache after adding favorite
    await update_filtered_calendar_cache(hass, entry)


async def remove_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
) -> None:
    """Remove a favorite from the collection and sync removal across all components.

    This function performs the complete flow for removing a favorite, including
    data cleanup, entity removal, and cache updates.

    Data Flow & Synchronization Points:
    1. Remove from config entry data → Triggers config entry listeners across platforms
    2. Remove entity from entity registry → Entity disappears from UI immediately
    3. Update calendar cache → Concert events removed from calendar entity

    UI Update Points:
    - Config entry update → All platforms receive removal notifications
    - Entity registry removal → Sensor entity disappears from UI immediately
    - Calendar cache update → Concert events disappear from calendar entity

    Args:
        hass: Home Assistant instance for entity registry access
        entry: Config entry to modify (triggers sync to other components)
        musicbrainz_id: Unique MusicBrainz identifier for the artist to remove

    Returns:
        None

    Raises:
        ServiceValidationError: When favorite with given MusicBrainz ID doesn't exist

    Side Effects:
        - Modifies entry.data["favorites"] → Triggers all config entry listeners
        - Removes entity from entity registry → Entity disappears from UI immediately
        - Updates calendar cache → Calendar entity refreshes without removed events
    """
    _LOGGER.debug("Removing favorite with MusicBrainz ID: %s", musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if the favorite exists
    if musicbrainz_id not in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID '{musicbrainz_id}' not found"
        )

    # Get the name for logging
    favorite_data = current_favorites[musicbrainz_id]
    variants = favorite_data.get("variants", [])
    favorite_name = variants[0] if variants else "Unknown"

    # Remove the favorite
    del current_favorites[musicbrainz_id]

    # Update the config entry
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "favorites": current_favorites}
    )

    # Remove the entity from entity registry
    entity_registry = er.async_get(hass)

    # Find and remove the entity for this favorite
    unique_id = f"favorite_{musicbrainz_id}"
    if entity_id := entity_registry.async_get_entity_id(
        "sensor", "music_favorites", unique_id
    ):
        entity_registry.async_remove(entity_id)

    _LOGGER.info("Successfully removed favorite: %s", favorite_name)

    # Update filtered calendar cache after removing favorite
    await update_filtered_calendar_cache(hass, entry)


async def resolve_artist_from_name(
    hass: HomeAssistant,
    artist_name: str,
) -> dict[str, Any] | None:
    """Resolve artist name to MusicBrainz ID using fuzzy matching and decision logic.

    This function is used by the conversation platform and services to convert
    user-provided artist names into precise MusicBrainz IDs for favorite management.
    It implements smart matching logic to handle exact matches vs. ambiguous cases.

    Search Logic:
    1. Query MusicBrainz API with artist name → Get up to 10 matches
    2. Analyze results → Apply decision rules based on match count and quality
    3. Return action for calling code → Either create immediately or prompt user choice

    UI Integration:
    - "create" action → Calling code can immediately add favorite
    - "choose" action → UI displays options for user selection
    - "not_found" action → UI shows "no matches" message

    Args:
        hass: Home Assistant instance for MusicBrainz API client access
        artist_name: User-provided artist name (from conversation, service call, etc.)

    Returns:
        Decision dictionary with one of:
        - {"action": "create", "name": "exact_name", "musicbrainz_id": "id"} - Exact match found, ready to add
        - {"action": "choose", "options": [{"name": "...", "musicbrainz_id": "..."}, ...]} - Multiple matches, user choice needed
        - {"action": "not_found"} - No matches found in MusicBrainz
        - None if MusicBrainz API error (temporary failure, should retry)

    Decision Rules:
        - Exactly 1 match + exact name match (case insensitive) → "create"
        - Multiple matches OR 1 match with different name → "choose"
        - No matches → "not_found"
    """
    _LOGGER.debug("Resolving artist name: '%s'", artist_name)

    try:
        client = MusicBrainzClient(hass)
        matches = await client.search_artists(artist_name, limit=10)

        _LOGGER.debug(
            "MusicBrainz returned %d matches for '%s'", len(matches), artist_name
        )

        # Case 1: No matches found
        if len(matches) == 0:
            _LOGGER.info("No MusicBrainz matches found for '%s'", artist_name)
            return {"action": "not_found"}

        # Case 2: Exactly 1 match AND exact name match (case insensitive)
        if len(matches) == 1 and matches[0]["name"].lower() == artist_name.lower():
            _LOGGER.info(
                "Exact match found for '%s': %s (%s)",
                artist_name,
                matches[0]["name"],
                matches[0]["id"],
            )
            return {
                "action": "create",
                "name": matches[0]["name"],  # Use the exact name from MusicBrainz
                "musicbrainz_id": matches[0]["id"],
                "aliases": matches[0].get("aliases", []),
            }

        # Case 3: Multiple matches OR single match with different name
        _LOGGER.info(
            "Multiple matches found for '%s', user needs to choose", artist_name
        )
        options = [
            {
                "name": match["name"],
                "musicbrainz_id": match["id"],
                "disambiguation": match.get("disambiguation", ""),
                "score": match.get("score", 0),
                "aliases": match.get("aliases", []),
            }
            for match in matches[:5]  # Limit to top 5 options
        ]

        return {"action": "choose", "options": options}  # noqa: TRY300, conflicts ´with RET505 🤷

    except MusicBrainzError as err:
        _LOGGER.error(
            "MusicBrainz API error while resolving '%s': %s", artist_name, err
        )
        return None
    except Exception:
        # Broad catch for any unexpected errors during artist resolution
        _LOGGER.exception("Unexpected error while resolving '%s'", artist_name)
        return None
