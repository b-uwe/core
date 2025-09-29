"""Select platform for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .calendar_utils import create_calendar_device_info, update_filtered_calendar_cache
from .const import DEFAULT_MAX_DISTANCE_KM, DISTANCE_FILTER_OPTIONS
from .datatypes import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)

# That's kinda bullshit because the select doesn't fetch anything. But... 🤷
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites select entities from a config entry."""
    _LOGGER.debug("Setting up Music Favorites select entities")

    # Create device info for calendar device (shared with calendar entity)
    device_info = create_calendar_device_info(entry.entry_id)

    # Create the distance filter select entity
    distance_filter_entity = DistanceFilterSelect(entry, device_info)
    async_add_entities([distance_filter_entity])

    _LOGGER.debug("Music Favorites select entities created")


class DistanceFilterSelect(SelectEntity):
    """Select entity for distance filtering concerts."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MusicFavoritesConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        self._entry = entry
        self._attr_name = "Distance Filter"
        self._attr_unique_id = f"{entry.entry_id}_distance_filter"
        self._attr_device_info = device_info
        # Read initial value from config entry data
        distance_filter = entry.data.get("distance_filter", DEFAULT_MAX_DISTANCE_KM)
        if distance_filter is None:
            self._attr_current_option = "No limit"
        else:
            self._attr_current_option = str(distance_filter)
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def options(self) -> list[str]:
        """Return the list of available options with km suffix for display."""
        return [
            option + " km" if option != "No limit" else option
            for option in DISTANCE_FILTER_OPTIONS
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current option with km suffix for display."""
        if self._attr_current_option == "No limit" or not self._attr_current_option:
            return "No limit"
        return f"{self._attr_current_option} km"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        return {
            "description": "Maximum distance from Home Assistant location to show concerts",
            "unit": "kilometers" if self.current_option != "No limit" else None,
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Strip " km" suffix to get internal value
        if option == "No limit":
            internal_option = "No limit"
        else:
            internal_option = option.replace(" km", "")

        self._attr_current_option = internal_option

        # Save to config entry data
        current_data = dict(self._entry.data)
        if internal_option == "No limit":
            current_data["distance_filter"] = None
        else:
            try:
                current_data["distance_filter"] = float(internal_option)
            except ValueError:
                _LOGGER.error("Invalid distance filter option: %s", option)
                return

        # Update config entry
        self.hass.config_entries.async_update_entry(self._entry, data=current_data)

        # Update filtered calendar cache after distance filter change
        await update_filtered_calendar_cache(self.hass, self._entry)

        self.async_write_ha_state()
        _LOGGER.debug("Distance filter changed to: %s", option)

    def get_distance_limit_km(self) -> float | None:
        """Get the current distance limit in kilometers.

        Returns:
            Distance limit in km, or None for no limit
        """
        if self.current_option == "No limit" or not self.current_option:
            return None
        try:
            return float(self.current_option)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid distance filter value: %s, using default", self.current_option
            )
            return float(DEFAULT_MAX_DISTANCE_KM)
