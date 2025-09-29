"""Utility functions for the Music Favorites integration."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEFAULT_MAX_DISTANCE_KM, DOMAIN, VERSION

if TYPE_CHECKING:
    from .datatypes import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)


def calculate_approximate_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate approximate distance between two lat/lng points in kilometers.

    Uses a simple approximation instead of haversine for better performance.
    Accuracy is sufficient for filtering concerts within reasonable distances.

    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point

    Returns:
        Distance in kilometers (approximate)
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
    """Create device info for the calendar device.

    Args:
        entry_id: Config entry ID

    Returns:
        DeviceInfo object for the calendar device
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
    """Update the filtered calendar events cache.

    This function does all the distance filtering and stores the results in runtime_data.
    It should be called whenever favorites or distance filter settings change.

    Args:
        hass: Home Assistant instance
        entry: Music Favorites config entry
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
    """Notify calendar entity to refresh after cache update."""
    # Calendar entity registers itself in runtime_data when added to hass
    if calendar_entity := entry.runtime_data.get("calendar_entity"):
        _LOGGER.debug("Refreshing calendar entity after cache update")
        calendar_entity.async_write_ha_state()
    else:
        _LOGGER.debug("Calendar entity not registered yet, skipping refresh")
