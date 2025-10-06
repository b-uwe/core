"""Utility functions for the Music Favorites integration."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEFAULT_MAX_DISTANCE_KM, DOMAIN, VERSION

if TYPE_CHECKING:
    from .models import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)


def calculate_approximate_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate approximate distance between two geographic points for event filtering.

    Implements a simplified distance calculation optimized for performance over precision.
    This approximation is sufficient for filtering concert events within reasonable
    distances from the Home Assistant location without the computational overhead
    of precise haversine calculations.

    Distance Calculation Method:
    - Latitude conversion: 1 degree ≈ 111 km (consistent globally)
    - Longitude conversion: 1 degree ≈ 111 km × cos(latitude) (varies by latitude)
    - Euclidean distance: sqrt(lat_diff² + lon_diff²) for final distance

    Args:
        lat1: Latitude of first point (typically HA location)
        lon1: Longitude of first point (typically HA location)
        lat2: Latitude of second point (typically concert venue)
        lon2: Longitude of second point (typically concert venue)

    Returns:
        float: Approximate distance in kilometers between the two points

    Used By:
        _should_include_event_by_distance() for filtering concert events by user distance preferences
    """
    # Simple lat/lng to km conversion
    # 1 degree latitude ≈ 111 km everywhere
    # 1 degree longitude ≈ 111 km * cos(latitude) (varies by latitude)

    lat_diff = lat2 - lat1
    lon_diff = lon2 - lon1

    # Use average latitude for longitude calculation
    avg_lat_rad = math.radians((lat1 + lat2) / 2)

    # Convert to approximate distance
    lat_km = lat_diff * 111.0  # 111 km per degree latitude
    lon_km = lon_diff * 111.0 * math.cos(avg_lat_rad)  # Adjust for longitude

    # Pythagorean theorem for straight-line distance
    distance = math.sqrt(lat_km**2 + lon_km**2)

    return abs(distance)


def create_calendar_device_info(entry_id: str) -> DeviceInfo:
    """Create shared device information for calendar and select entities grouping.

    Generates device metadata that groups related entities (calendar and distance filter)
    under a single "Concert Calendar" device in the Home Assistant UI. This provides logical
    organization for user-facing configuration entities.

    Args:
        entry_id: Config entry ID for unique device identification across restarts

    Returns:
        DeviceInfo: Device information object for entity device association

    Used By:
        - calendar.py async_setup_entry() → Associates calendar entity with settings device
        - select.py async_setup_entry() → Associates distance filter entity with same device
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_calendar")},
        name="Concert Calendar",
        manufacturer="Music Favorites Integration",
        model="Event Calendar",
        sw_version=VERSION,
        configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
    )


async def update_filtered_calendar_cache(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> None:
    """Rebuild and cache distance-filtered concert events for calendar display with synchronization.

    This function is the central hub for calendar event processing, collecting events from
    all favorites, applying distance filtering based on user preferences, and caching
    results for efficient calendar access. It triggers UI updates when processing completes.

    Cache Rebuild Process:
    1. Extract events from all favorites → Collect concert data from coordinator updates
    2. Add performer metadata → Enhance events with artist names and MusicBrainz IDs
    3. Apply distance filtering → Filter events based on user distance preference
    4. Cache filtered results → Store in runtime_data for calendar entity access
    5. Notify calendar entity → Trigger UI refresh with new event data

    Distance Filtering Logic:
    - Uses HA location as center point → Home Assistant configured latitude/longitude
    - Applies user distance filter → From select entity or config entry setting
    - Includes events without coordinates → Fallback behavior for incomplete data
    - Logs filtering statistics → Debugging and monitoring information

    Synchronization Points:
    - Called by coordinator → When new events fetched from APIs
    - Called by select entity → When user changes distance filter
    - Triggers calendar refresh → Calendar entity updates immediately via async_write_ha_state()

    Args:
        hass: Home Assistant instance providing location configuration and entity access
        entry: Config entry containing favorites data and distance filter settings

    Returns:
        None

    Side Effects:
        - Updates runtime_data cache → New filtered events available for calendar
        - Triggers calendar refresh → Calendar entity updates in UI immediately
        - Logs filtering statistics → Performance and debugging information
    """
    _LOGGER.debug("Updating filtered calendar events cache")

    all_events = []
    favorites_data = entry.data.get("favorites", {})

    # Get distance filter setting from config entry data
    distance_limit_km = entry.data.get("distance_filter", DEFAULT_MAX_DISTANCE_KM)
    if distance_limit_km is None:
        _LOGGER.debug("Distance filter: No limit")
    else:
        _LOGGER.debug("Distance filter: %s km", distance_limit_km)

    # Get Home Assistant location for distance filtering
    ha_latitude = hass.config.latitude
    ha_longitude = hass.config.longitude

    events_total = 0
    events_filtered = 0

    for musicbrainz_id, favorite_data in favorites_data.items():
        events_data = favorite_data.get("events", [])
        variants = favorite_data.get("variants", [])
        performer_name = variants[0] if variants else "Unknown Artist"

        # Add performer info to each event for calendar display
        for event in events_data:
            events_total += 1
            event_with_performer = event.copy()
            event_with_performer["performer_name"] = performer_name
            event_with_performer["musicbrainz_id"] = musicbrainz_id

            # Apply distance filter if enabled and coordinates are available
            if _should_include_event_by_distance(
                event_with_performer, distance_limit_km, ha_latitude, ha_longitude
            ):
                all_events.append(event_with_performer)
            else:
                events_filtered += 1

    _LOGGER.debug(
        "Distance filtering: %d events total, %d events filtered out, %d events cached",
        events_total,
        events_filtered,
        len(all_events),
    )

    # Store filtered events in runtime_data cache
    entry.runtime_data["filtered_calendar_events"] = all_events

    # Notify calendar entity to refresh (if it exists)
    await _notify_calendar_entity(hass, entry)


def _should_include_event_by_distance(
    event: dict[str, Any],
    distance_limit_km: float | None,
    ha_latitude: float | None,
    ha_longitude: float | None,
) -> bool:
    """Check if event should be included based on distance filtering.

    Args:
        event: Event data with potential latitude/longitude
        distance_limit_km: Distance limit in km, or None for no limit
        ha_latitude: Home Assistant latitude
        ha_longitude: Home Assistant longitude

    Returns:
        True if event should be included, False if filtered out
    """
    # Always include if no distance limit is set
    if distance_limit_km is None:
        return True

    # Always include if HA location is not configured
    if ha_latitude is None or ha_longitude is None:
        _LOGGER.debug("HA location not configured, including all events")
        return True

    # Always include events without coordinates (fallback behavior)
    event_latitude = event.get("latitude")
    event_longitude = event.get("longitude")
    if event_latitude is None or event_longitude is None:
        return True

    try:
        # Calculate distance and filter
        distance = calculate_approximate_distance(
            ha_latitude, ha_longitude, float(event_latitude), float(event_longitude)
        )
        include = distance <= distance_limit_km

    except (ValueError, TypeError) as err:
        _LOGGER.error(
            "Failed to calculate distance for event '%s': %s",
            event.get("text", "Unknown Event"),
            err,
        )
        # Include event if distance calculation fails
        return True

    return include


async def _notify_calendar_entity(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> None:
    """Trigger immediate calendar entity UI refresh after filtered events cache rebuild.

    This function provides the final synchronization step in the calendar update pipeline,
    ensuring that UI changes are immediately visible to users after distance filtering
    or event data changes. It maintains the loose coupling between cache management
    and entity UI updates through the runtime_data registry pattern.

    Synchronization Chain Position:
    - Triggered by: update_filtered_calendar_cache() after cache rebuild completion
    - Triggers: calendar_entity.async_write_ha_state() for immediate UI refresh
    - Timing: Always called at end of cache update operations, never standalone

    Entity Registration Pattern:
    - Calendar entity self-registers → Stores reference in runtime_data during async_added_to_hass()
    - Graceful degradation → Skips refresh if calendar entity not yet loaded/registered
    - Reference management → No manual cleanup needed (handled by config entry lifecycle)

    UI Update Mechanism:
    - Direct state refresh → async_write_ha_state() bypasses coordinator scheduling
    - Immediate visibility → Calendar events appear in UI without waiting for next coordinator cycle
    - Event loop safety → Called from async context, safe for immediate execution

    Args:
        hass: Home Assistant instance providing async execution context and logging
        entry: Config entry containing runtime_data registry with calendar entity reference

    Returns:
        None

    Side Effects:
        - Triggers calendar entity state refresh → UI updates immediately visible
        - Logs notification activity → Debugging visibility for synchronization troubleshooting
        - No data modification → Pure notification mechanism without cache changes

    Called By:
        - update_filtered_calendar_cache() → Final step after cache rebuild and statistics logging
        - Never called independently → Always part of larger cache update operation
    """
    # Calendar entity registers itself in runtime_data when added to hass
    if calendar_entity := entry.runtime_data.get("calendar_entity"):
        _LOGGER.debug("Refreshing calendar entity after cache update")
        calendar_entity.async_write_ha_state()
    else:
        _LOGGER.debug("Calendar entity not registered yet, skipping refresh")
