"""Sensor platform for the Music Favorites integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, VERSION
from .datatypes import MusicFavoritesConfigEntry
from .models import BAND_STATUS_ICONS, BandStatus

_LOGGER = logging.getLogger(__name__)

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


class EntityManager:
    """Manages dynamic entity addition and removal for the Music Favorites integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MusicFavoritesConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity manager."""
        self.hass = hass
        self.entry = entry
        self._async_add_entities = async_add_entities
        self._device_info = device_info

    @callback
    def add_favorite_entity(
        self, musicbrainz_id: str, favorite_data: dict[str, Any]
    ) -> None:
        """Add a new favorite entity."""
        favorite_variants = favorite_data.get("variants", [])
        display_name = favorite_variants[0] if favorite_variants else "Unknown"

        _LOGGER.debug(
            "add_favorite_entity called for %s (%s)",
            display_name,
            musicbrainz_id,
        )

        # Check if entity already exists by looking at entity registry
        entity_registry = er.async_get(self.hass)
        unique_id = f"favorite_{musicbrainz_id}"

        if entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id):
            _LOGGER.debug(
                "Entity for %s already exists in registry, skipping",
                display_name,
            )
            return

        # Entity doesn't exist, create it
        entity = FavoriteSensor(
            musicbrainz_id, favorite_data, self._device_info, self.entry
        )
        self._async_add_entities([entity])
        _LOGGER.debug("Entity created and added for %s", display_name)


class FavoriteSensor(SensorEntity):
    """Sensor for a single favorite."""

    def __init__(
        self,
        favorite_key: str,
        favorite_data: dict[str, Any],
        device_info: DeviceInfo,
        entry: MusicFavoritesConfigEntry,
    ) -> None:
        """Initialize the favorite sensor."""
        self._favorite_key = favorite_key
        self._entry = entry

        # Get the display name from initial data (for entity setup)
        favorite_variants = favorite_data.get("variants", [])
        display_name = favorite_variants[0] if favorite_variants else "Unknown"

        # Set entity name to just the band/artist name
        self._attr_name = display_name

        self._attr_unique_id = f"favorite_{favorite_key}"
        self._attr_device_info = device_info

        # Create entity ID as "music_favorites_act_{name.lower()}"
        safe_name = re.sub(r"[^\w\s-]", "", display_name.lower())
        safe_name = re.sub(r"[-\s]+", "_", safe_name).strip("_")
        # Set entity_id directly instead of _attr_entity_id
        self.entity_id = f"sensor.music_favorites_act_{safe_name}"

        self._attr_has_entity_name = False

    @property
    def _current_favorite_data(self) -> dict[str, Any]:
        """Get current favorite data from config entry."""
        favorites: dict[str, Any] = self._entry.data.get("favorites", {})
        favorite_data: dict[str, Any] = favorites.get(self._favorite_key, {})
        return favorite_data

    @property
    def icon(self) -> str:
        """Return the icon based on current status."""
        current_data = self._current_favorite_data
        status = current_data.get("status", BandStatus.UNKNOWN)
        return BAND_STATUS_ICONS.get(status, "mdi:help-circle")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Attributes of the entity."""
        current_data = self._current_favorite_data
        variants = current_data.get("variants", [])

        attributes = {
            "musicbrainz_id": self._favorite_key,
            "variants": variants[1:]
            if len(variants) > 1
            else [],  # All except display name
        }

        # Add all relation links as individual attributes
        attributes.update(
            {
                key: value
                for key, value in current_data.items()
                if key.endswith("_url")  # Only include relation URL attributes
            }
        )

        return attributes

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        # Return the band status as the primary state
        current_data = self._current_favorite_data
        status = current_data.get("status", BandStatus.UNKNOWN)
        return str(status)

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        await super().async_added_to_hass()

        # Listen for config entry updates to refresh sensor when data changes
        self.async_on_remove(
            self._entry.add_update_listener(self._config_entry_updated)
        )

    async def _config_entry_updated(
        self, hass: HomeAssistant, entry: MusicFavoritesConfigEntry
    ) -> None:
        """Handle config entry updates."""
        # Schedule update to refresh entity attributes and state
        self.async_schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites sensors from a config entry."""

    # Create device info for all entities
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_acts")},
        name="Top Acts",
        manufacturer="Music Favorites Integration",
        model="Bands & Artists Collection",
        sw_version=VERSION,
        configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
    )

    # Create entity manager and store it in runtime_data for dynamic management
    entity_manager = EntityManager(hass, entry, async_add_entities, device_info)
    entry.runtime_data["entity_manager"] = entity_manager

    # Create entities for all existing favorites in config data
    favorites_data = entry.data.get("favorites", {})
    initial_entities = []
    for musicbrainz_id, favorite_data in favorites_data.items():
        entity = FavoriteSensor(musicbrainz_id, favorite_data, device_info, entry)
        initial_entities.append(entity)

    if initial_entities:
        async_add_entities(initial_entities)
