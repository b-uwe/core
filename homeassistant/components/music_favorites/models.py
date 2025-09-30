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


# Status icons mapping
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
                # Keep original if parsing fails
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
    previous_status: BandStatus | None = None,
) -> BandStatus:
    """Determine the status of a band based on MusicBrainz data.

    Args:
        artist_data: Artist data from MusicBrainz API
        events_data: Events data from MusicBrainz API (optional)
        previous_status: Previous status for reformed detection (optional)

    Returns:
        BandStatus enum value
    """
    # Check if band has ended (disbanded)
    life_span = artist_data.get("life-span", {})
    end_date = life_span.get("end")

    if end_date:
        # Check if this was previously disbanded and now active (reformed)
        if previous_status == BandStatus.DISBANDED:
            return BandStatus.REFORMED
        return BandStatus.DISBANDED

    # Band is active - check tour status
    if events_data:
        tour_status = get_tour_status(events_data)
        if tour_status:
            return tour_status

    # Default to active
    return BandStatus.ACTIVE


def get_tour_status(events_data: list[dict[str, Any]]) -> BandStatus | None:
    """Check tour status based on events data.

    Args:
        events_data: List of events from future event sources

    Returns:
        BandStatus.ON_TOUR, BandStatus.TOUR_PLANNED, or None
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

            # Check if currently on tour (within active window)
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


# The main favorites storage - structure with variants and relation links
# Format: {"MusicBrainz ID": {"variants": ["Display Name", "variant1", ...], "allmusic_url": "...", ...}}
favorites: dict[str, dict[str, Any]] = {}


async def add_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
) -> None:
    """Add a new favorite to the collection."""
    _LOGGER.debug("Adding favorite with MusicBrainz ID: %s", musicbrainz_id)

    # Get current favorites
    current_favorites = dict(entry.data.get("favorites", {}))

    # Check if already exists
    if musicbrainz_id in current_favorites:
        raise ServiceValidationError(
            f"Favorite with MusicBrainz ID {musicbrainz_id} already exists"
        )

    # Fetch complete artist data from MusicBrainz (sequential calls to be nice to their servers)
    client = MusicBrainzClient(hass)
    try:
        artist_data = await client.get_artist_by_id(musicbrainz_id)
    except MusicBrainzError as err:
        _LOGGER.error("Failed to fetch artist data for %s: %s", musicbrainz_id, err)
        raise ServiceValidationError(
            f"Could not fetch artist data from MusicBrainz: {err}"
        ) from err

    # Extract name and aliases from MusicBrainz response
    name = artist_data["name"]
    aliases = [
        alias.get("name", "")
        for alias in artist_data.get("aliases", [])
        if alias.get("name")  # Only include non-empty alias names
    ]

    # Extract relation links
    relation_links = extract_relation_links(artist_data)

    # Initialize events data - will be populated from Bandsintown if available
    events_data: list[dict[str, Any]] = []

    # Extract LD+JSON data from Bandsintown URL if available
    bandsintown_url = relation_links.get("bandsintown_url")
    if bandsintown_url:
        _LOGGER.debug(
            "Found Bandsintown URL, extracting LD+JSON data: %s", bandsintown_url
        )
        try:
            ldjson_data = await fetch_and_extract_ldjson(hass, bandsintown_url)

            # Parse MusicEvents and use them for status determination
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
        _LOGGER.debug("No Bandsintown URL found for artist %s", name)

    # Determine band status with events data (now using Bandsintown events if available)
    band_status = determine_band_status(artist_data, events_data)

    # Add new favorite with name, aliases, and relation links from MusicBrainz
    # Deduplicate variants using a set while preserving order (name first)
    variants_set = {name}
    favorite_variants = [name]

    if aliases:
        for alias in aliases:
            if alias not in variants_set:
                variants_set.add(alias)
                favorite_variants.append(alias)

    # Store variants, status, events, and flatten relation links directly into the data structure
    favorite_data = {
        "variants": favorite_variants,
        "status": band_status,
        "events": events_data,  # Store events data with the act
        "musicbrainz_url": f"https://musicbrainz.org/artist/{musicbrainz_id}",
        **relation_links,  # Flatten relation links  into the object
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
            _LOGGER.debug("Calling entity_manager.add_favorite_entity for %s", name)
            entity_manager.add_favorite_entity(musicbrainz_id, favorite_data)
        else:
            _LOGGER.warning(
                "Entity manager not found in runtime_data - new entity will not be created immediately"
            )
    else:
        _LOGGER.warning(
            "No runtime_data available - new entity will not be created immediately"
        )

    _LOGGER.info("Successfully added favorite: %s", name)

    # Update filtered calendar cache after adding favorite
    await update_filtered_calendar_cache(hass, entry)


async def remove_favorite(
    hass: HomeAssistant,
    entry: ConfigEntry,
    musicbrainz_id: str,
) -> None:
    """Remove a favorite from the collection."""
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
    """Resolve artist name to MusicBrainz ID using the decision logic.

    Args:
        hass: Home Assistant instance
        artist_name: The artist name to search for

    Returns:
        Dictionary with one of:
        - {"action": "create", "name": "exact_name", "musicbrainz_id": "id"} - Exact match found
        - {"action": "choose", "options": [{"name": "...", "musicbrainz_id": "..."}, ...]} - Multiple matches
        - {"action": "not_found"} - No matches found
        - None if MusicBrainz API error
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
