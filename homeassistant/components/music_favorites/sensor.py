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

# Serialize entity updates for API rate limiting
PARALLEL_UPDATES = 1


class EntityManager:
    """Manages dynamic entity addition for the Music Favorites integration.

    This class handles the creation of sensor entities when favorites are added dynamically
    through service calls. It ensures entities appear immediately in the UI without requiring
    a restart or platform reload.

    Synchronization Role:
    - Called by add_favorite() service → Creates entity immediately when favorite added
    - Checks entity registry → Prevents duplicate entity creation
    - Triggers UI updates → New entity appears in UI instantly via async_add_entities
    - Stores reference in runtime_data → Available for future entity management operations

    Architectural Note - Why No remove_favorite_entity() Method:
    Entity removal uses a different architectural pattern and doesn't require EntityManager:
    - Add entities: Requires async_add_entities callback (stored in EntityManager)
    - Remove entities: Uses Home Assistant's global entity registry directly
    - The entity registry is accessible anywhere via er.async_get(hass)
    - Entities are removed by calling entity_registry.async_remove(entity_id)
    - This asymmetry is intentional and follows Home Assistant's design patterns
    - See remove_favorite() in models.py for the direct registry removal implementation
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MusicFavoritesConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the entity manager with references for dynamic entity creation.

        Sets up the infrastructure needed to create sensor entities on-demand when
        favorites are added via service calls. This enables immediate UI updates
        without requiring integration reloads.

        Entity Creation Infrastructure:
        - Stores async_add_entities callback → Used to register new entities with HA
        - Stores device_info reference → Ensures consistent device grouping in UI
        - Stores config entry reference → Enables access to current favorites data
        - Stores hass reference → Provides access to entity registry for duplicate checks

        Args:
            hass: Home Assistant instance for entity registry access and service integration
            entry: Config entry containing favorites data and serving as central data store
            async_add_entities: HA callback to register new entities and trigger UI updates
            device_info: Shared device information for grouping all favorite entities

        Returns:
            None

        Side Effects:
            - Stores references needed for future dynamic entity creation
            - No entities created during initialization → Entities created later via add_favorite_entity()
        """
        self.hass = hass
        self.entry = entry
        self._async_add_entities = async_add_entities
        self._device_info = device_info

    @callback
    def add_favorite_entity(
        self, musicbrainz_id: str, favorite_data: dict[str, Any]
    ) -> None:
        """Add a new favorite entity dynamically and trigger immediate UI update.

        This method is called by the add_favorite service to create sensor entities
        on-demand without requiring a platform reload. It ensures new favorites appear
        in the UI immediately after being added via service calls.

        UI Update Flow:
        1. Check entity registry → Prevent duplicate entity creation
        2. Create FavoriteSensor instance → Initialize with current favorite data
        3. Call async_add_entities → Entity appears in UI immediately
        4. Entity registers config entry listener → Receives future updates automatically

        Args:
            musicbrainz_id: Unique MusicBrainz identifier for the artist (used in unique_id)
            favorite_data: Complete favorite data dict with variants, status, events, etc.

        Returns:
            None

        Side Effects:
            - Creates new sensor entity → Entity appears in UI immediately
            - Entity auto-registers for config entry updates → Receives future data changes
        """
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
    """Sensor entity representing a single favorite artist with dynamic state updates.

    This entity displays the current status of a favorite artist (Active, On Tour, etc.)
    and synchronizes automatically with external data sources via config entry updates.
    Each sensor represents one favorite and updates its state based on MusicBrainz and
    Bandsintown data refreshed by the coordinator.

    Data Synchronization:
    - Reads from entry.data["favorites"] → Always gets fresh data from config entry
    - Updates via config entry listeners → Registers listener in async_added_to_hass() for automatic refresh
    - State changes trigger UI updates → async_schedule_update_ha_state() called on config entry changes
    - Icon changes based on status → Visual feedback for tour status changes

    State Management:
    - native_value: Current band status (Active, On Tour, Disbanded, etc.)
    - icon: Dynamic icon based on status (mdi:guitar-electric, mdi:bus-marker, etc.)
    - extra_state_attributes: Additional data like events, URLs, variants
    """

    def __init__(
        self,
        favorite_key: str,
        favorite_data: dict[str, Any],
        device_info: DeviceInfo,
        entry: MusicFavoritesConfigEntry,
    ) -> None:
        """Initialize a favorite sensor entity with initial data and unique identification.

        Creates a sensor entity representing one favorite artist, setting up the entity's
        identity, naming, and initial state. The entity will automatically sync with
        config entry updates after being added to Home Assistant.

        Entity Setup Process:
        1. Store config entry reference → Enables future data access
        2. Extract display name from variants → Primary artist name for entity naming
        3. Generate unique entity ID → Ensures entity survives restarts and reloads
        4. Set device association → Groups entity under shared device in UI

        Synchronization Setup:
        - Stores Config Entry reference → Used by all properties to read current data
        - Entity will register config listeners → Happens later in async_added_to_hass()
        - Real-time data access → Properties always read fresh data from config entry

        Args:
            favorite_key: MusicBrainz ID used as unique identifier for this favorite
            favorite_data: Initial favorite data dict (used only for entity setup, not ongoing data)
            device_info: Shared device info for grouping related entities in UI
            entry: Config entry reference for accessing current data and registering listeners

        Returns:
            None

        Side Effects:
            - Sets entity unique_id, name, and entity_id for HA registration
            - Creates entity_id with sanitized artist name for user-friendly identification
            - Stores references needed for future data synchronization
        """
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
        """Get current favorite data from config entry.

        This property provides real-time access to the favorite's data by reading
        directly from the config entry. This ensures entities always display the
        most current information after coordinator updates.

        Synchronization Point:
        - Always reads from entry.data → Gets fresh data immediately after coordinator updates
        - Called by all entity properties → Ensures UI displays current status, events, URLs
        - No caching → Every access gets latest data from central store

        Returns:
            dict: Complete favorite data including variants, status, events, relation URLs
                 Returns empty dict if favorite was removed from config entry
        """
        favorites: dict[str, Any] = self._entry.data.get("favorites", {})
        favorite_data: dict[str, Any] = favorites.get(self._favorite_key, {})
        return favorite_data

    @property
    def icon(self) -> str:
        """Return dynamic icon based on current band status.

        The icon changes automatically to reflect the band's current activity status,
        providing visual feedback in the UI when coordinator updates band status.

        Icon Mapping:
        - Active: mdi:guitar-electric
        - On Tour: mdi:bus-marker
        - Disbanded: mdi:music-off
        - Reformed: mdi:set-none
        - Tour Planned: mdi:bus-clock
        - Unknown: mdi:help-circle (fallback)

        UI Update Trigger:
        - Called when async_schedule_update_ha_state() triggered by config entry changes
        - Icon changes appear immediately in dashboard when band status changes

        Returns:
            str: Material Design icon identifier representing current band status
        """
        current_data = self._current_favorite_data
        status = current_data.get("status", BandStatus.UNKNOWN)
        return BAND_STATUS_ICONS.get(status, "mdi:help-circle")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional entity attributes with detailed band information.

        Provides rich metadata about the favorite artist that updates automatically
        when coordinator fetches fresh data from external APIs.

        Attribute Categories:
        - Basic Info: musicbrainz_id (unique identifier)
        - Name Variants: All known names/aliases (except primary display name)
        - External Links: All relation URLs (bandsintown_url, allmusic_url, etc.)

        Synchronization Behavior:
        - Updates when config entry changes → New URLs appear when MusicBrainz relations change
        - Relation URLs added/removed automatically → Coordinator updates MusicBrainz data
        - Always current data via _current_favorite_data → No stale attribute values

        Returns:
            Mapping: Dictionary of attribute name to value pairs for entity details panel
                    Returns dynamic relation URLs that may change over time
        """
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
        """Return the primary state value representing the favorite artist's current status.

        This property provides the main sensor state that appears in the UI as the entity's
        current value. The state reflects the band's activity level and tour status based
        on MusicBrainz data and upcoming events from Bandsintown.

        State Values:
        - "Active" → Band is currently active with no specific tour information
        - "On Tour" → Band has confirmed upcoming tour dates
        - "Tour Planned" → Band has announced tour dates for the future
        - "Disbanded" → Band has officially disbanded according to MusicBrainz
        - "Reformed" → Previously disbanded band has reformed
        - "Unknown" → Status cannot be determined from available data

        Data Source:
        - Reads from _current_favorite_data → Always gets fresh status from config entry
        - Updates automatically → State changes when coordinator updates band status
        - Fallback handling → Returns "Unknown" if status missing from data

        UI Integration:
        - Primary sensor display → Shows as main entity value in dashboard
        - State changes trigger updates → UI refreshes when status changes via coordinator
        - Consistent string format → Always returns string representation for HA compatibility

        Returns:
            str: String representation of current band status for UI display
                 Never returns None due to fallback to BandStatus.UNKNOWN
        """
        # Return the band status as the primary state
        current_data = self._current_favorite_data
        status = current_data.get("status", BandStatus.UNKNOWN)
        return str(status)

    async def async_added_to_hass(self) -> None:
        """Register entity with Home Assistant and set up automatic synchronization.

        This lifecycle method is called by Home Assistant after the entity has been
        successfully added to the entity registry and is ready to receive updates.
        It establishes the critical synchronization link between config entry changes
        and entity UI updates.

        Synchronization Setup:
        - Registers config entry update listener → Entity receives notifications when coordinator updates data
        - Uses async_on_remove() → Ensures listener is automatically cleaned up when entity removed
        - Enables real-time UI updates → Entity refreshes immediately when favorites data changes

        Update Flow Established:
        1. Coordinator updates favorite data → Calls hass.config_entries.async_update_entry()
        2. Config entry change triggers → All registered listeners including this entity
        3. _config_entry_updated() called → Entity schedules UI state update
        4. Entity properties re-read → Fresh data from entry.data displayed in UI

        Args:
            None

        Returns:
            None

        Side Effects:
            - Registers config entry update listener → Enables automatic synchronization
            - Sets up cleanup callback → Listener removed when entity unloaded
            - Entity becomes responsive to data changes → UI updates when coordinator fetches new data
        """
        await super().async_added_to_hass()

        # Listen for config entry updates to refresh sensor when data changes
        self.async_on_remove(
            self._entry.add_update_listener(self._config_entry_updated)
        )

    async def _config_entry_updated(
        self, _hass: HomeAssistant, _entry: MusicFavoritesConfigEntry
    ) -> None:
        """Handle config entry updates and trigger UI refresh.

        This callback is triggered whenever the config entry data changes, ensuring
        the entity immediately reflects updated information in the UI.

        Trigger Sources:
        - Coordinator updates → New band status, events, or relation URLs
        - Service calls → add_favorite, remove_favorite updates
        - Configuration changes → Distance filter or other settings

        UI Update Flow:
        1. Config entry updated → This callback triggered immediately
        2. async_schedule_update_ha_state() → Queues entity refresh on next event loop
        3. Properties re-evaluated → icon, native_value, extra_state_attributes refreshed
        4. UI updates → Changes appear in dashboard without manual refresh

        Args:
            hass: Home Assistant instance (required by HA callback signature)
            entry: Updated config entry with fresh data

        Returns:
            None

        Side Effects:
            - Schedules UI state update → Entity refreshes in dashboard
            - All entity properties re-read entry.data → Displays fresh information
        """
        # Schedule update to refresh entity attributes and state
        self.async_schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicFavoritesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Favorites sensor platform from a config entry.

    This function is called by Home Assistant when the sensor platform is loaded.
    It creates the initial sensor entities for existing favorites and sets up the
    infrastructure for dynamic entity management.

    Setup Flow:
    1. Create shared device info → Groups all favorite sensors under one device
    2. Create entity manager → Enables dynamic entity creation for new favorites
    3. Store entity manager in runtime_data → Makes it available for service calls
    4. Create initial entities → One sensor per existing favorite in config data
    5. Add entities to HA → Sensors appear in UI immediately

    Entity Synchronization:
    - Each entity registers config entry listener → Automatic updates when coordinator changes data.
      Registration happens in HA internal functions triggered by async_add_entities()
    - Entity manager stored in runtime_data → Used by add_favorite service for dynamic creation
    - Entities read from entry.data → Always get fresh data from config entry

    Args:
        hass: Home Assistant instance for entity management
        entry: Config entry containing favorites data and serving as data store
        async_add_entities: Callback to register new entities with Home Assistant

    Returns:
        None

    Side Effects:
        - Creates sensor entities → Entities appear in UI immediately
        - Stores entity manager in entry.runtime_data → Available for dynamic entity creation
        - Entities register config entry listeners → Automatic updates when data changes
    """

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
