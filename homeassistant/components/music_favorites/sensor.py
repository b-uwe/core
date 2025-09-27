"""Sensor platform for the Music Favorites integration."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, VERSION
from .types import MusicFavoritesConfigEntry

# Serialize entity updates for future API rate limiting
PARALLEL_UPDATES = 1


class EntityManager:
    """Manages dynamic entity addition and removal for the Music Favorites integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MusicFavoritesConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Initialize the entity manager."""
        self.hass = hass
        self.entry = entry
        self._async_add_entities = async_add_entities
        self._added_entities: set[str] = set()

        # Cache device info for consistent entity assignment
        self._bands_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_acts")},
            name="Top Acts",
            manufacturer="Music Favorites Integration",
            model="Bands & Artists Collection",
            sw_version=VERSION,
            configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
        )

    @callback
    def add_favorite_entity(
        self, musicbrainz_id: str, favorite_variants: list[str]
    ) -> None:
        """Add a new favorite entity."""
        if musicbrainz_id not in self._added_entities:
            entity = FavoriteSensor(
                musicbrainz_id, favorite_variants, self._bands_device_info
            )
            self._async_add_entities([entity])
            self._added_entities.add(musicbrainz_id)

    @callback
    def sync_entities_with_config(self) -> None:
        """Synchronize entities with current config entry data.

        This handles both additions and ensures we track existing entities.
        """
        favorites_data: dict[str, list[str]] = self.entry.data.get("favorites", {})

        # Add any new entities that aren't already tracked
        new_entities = []
        for musicbrainz_id, favorite_variants in favorites_data.items():
            if musicbrainz_id not in self._added_entities:
                entity = FavoriteSensor(
                    musicbrainz_id, favorite_variants, self._bands_device_info
                )
                new_entities.append(entity)
                self._added_entities.add(musicbrainz_id)

        if new_entities:
            self._async_add_entities(new_entities)


class FavoriteSensor(SensorEntity):
    """Sensor for a single favorite."""

    def __init__(
        self, favorite_key: str, favorite_variants: list[str], device_info: DeviceInfo
    ) -> None:
        """Initialize the favorite sensor."""
        self._favorite_key = favorite_key
        self._favorite_variants = favorite_variants
        self._attr_name = favorite_variants[0]  # Display name for the entity
        self._attr_translation_key = "favorite_act"  # Translation key
        self._attr_unique_id = f"favorite_{favorite_key}"
        self._attr_device_info = device_info
        # Create human-readable entity ID for easy YAML reference
        # I rely on HA default behavior for duplicate entity ID's because
        # what I had in mind to do, was basically the same
        safe_name = re.sub(r"[^\w\s-]", "", favorite_variants[0].lower())
        safe_name = re.sub(r"[-\s]+", "_", safe_name).strip("_")
        self._attr_entity_id = f"sensor.music_favorites_{safe_name}"
        self._attr_icon = "mdi:guitar-electric"
        self._attr_has_entity_name = True

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Attributes of the entity."""
        return {
            "musicbrainz_id": self._favorite_key,
            "variants": self._favorite_variants[1:],  # All except display name
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        # For now, just return the favorite name
        # Later: could be "next concert date" or "tour status"
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites sensors from a config entry."""

    # Create entity manager and store it in runtime_data for dynamic management
    entity_manager = EntityManager(hass, entry, async_add_entities)
    entry.runtime_data["entity_manager"] = entity_manager

    # Synchronize with current config entry data (adds all existing favorites)
    entity_manager.sync_entities_with_config()
