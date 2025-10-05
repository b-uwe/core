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
    """Set up select platform from config entry with distance filter control entity.

    Creates a distance filter select entity that allows users to control the maximum
    distance for concert event filtering. This entity integrates with the calendar
    platform to provide real-time event filtering based on distance from HA location.

    Select Platform Setup:
    1. Create shared device info → Groups select with calendar under "Settings" device
    2. Create distance filter entity → Select entity for distance control
    3. Register entity → Entity appears in UI and connects to filtering system

    Distance Filter Integration:
    - User changes distance → async_select_option() updates config entry
    - Config entry update → Triggers calendar cache refresh via calendar_utils
    - Calendar refreshes → Events re-filtered and displayed based on new distance

    Args:
        hass: Home Assistant instance for entity registration and location services
        entry: Config entry containing distance setting and serving as central configuration
        async_add_entities: HA callback to register select entity and trigger UI appearance

    Returns:
        None

    Side Effects:
        - Creates distance filter entity → Entity appears in settings UI immediately
        - Sets up device grouping → Select grouped with calendar under settings device
        - Connects to filtering system → Distance changes trigger automatic event filtering
    """
    _LOGGER.debug("Setting up Music Favorites select entities")

    # Create device info for calendar device (shared with calendar entity)
    device_info = create_calendar_device_info(entry.entry_id)

    # Create the distance filter select entity
    distance_filter_entity = DistanceFilterSelect(entry, device_info)
    async_add_entities([distance_filter_entity])

    _LOGGER.debug("Music Favorites select entities created")


class DistanceFilterSelect(SelectEntity):
    """Select entity for controlling maximum distance filter for concert event display.

    This entity provides a user interface for configuring the distance-based filtering
    of concert events in the calendar entity. Users can select from predefined distance
    options or choose "No limit" to see all events regardless of distance from their
    Home Assistant location.

    Distance Filter Integration:
    - Reads current setting from config entry → Initializes with saved user preference
    - Updates config entry on change → Persists user selection across restarts
    - Triggers calendar cache refresh → Events immediately re-filtered when distance changes
    - Integrates with calendar_utils → Uses geolocation calculations for event filtering

    UI Behavior:
    - Dropdown selection → Multiple distance options (25km, 50km, 100km, 200km, "No limit")
    - Immediate effect → Calendar events update instantly when selection changes
    - Persistent setting → Selection saved in config entry and survives restarts
    - Device grouping → Appears alongside calendar entity under "Settings" device

    Synchronization Flow:
    1. User selects new distance → async_select_option() called by HA
    2. Config entry updated → Triggers config entry listeners across all platforms
    3. Calendar cache refreshed → update_filtered_calendar_cache() recalculates event distances
    4. Calendar entity updated → Events re-filtered and displayed based on new distance
    5. UI refreshes → New events appear/disappear in calendar immediately

    Distance Calculation:
    - Uses HA location → Home Assistant's configured latitude/longitude as center point
    - Very simplified distance calculation → Via calendar_utils.calculate_distance()
    - Event coordinates → Venue latitude/longitude from Bandsintown API data
    - Filter application → Only events within selected distance shown in calendar
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MusicFavoritesConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize distance filter select entity with current config and device grouping.

        Sets up the select entity that controls the maximum distance for concert event
        filtering. The entity reads the current distance setting from config entry data
        and provides a user interface for modifying the filter distance.

        Entity Configuration:
        - Name: "Distance Filter" → Clear purpose identification in UI
        - Unique ID: Based on config entry → Survives restarts and reloads
        - Device grouping → Groups with calendar under "Settings" device
        - Icon: "mdi:map-marker-radius" → Visual indication of distance/location functionality

        Current Value Setup:
        - Reads from entry.data["distance_filter"] → Current user-configured distance
        - Handles None value → Converts to "No limit" display option
        - Stores internal format → Numeric value without "km" suffix for processing

        Args:
            entry: Config entry containing current distance filter setting and central data store
            device_info: Shared device info for grouping with calendar entity in UI

        Returns:
            None

        Side Effects:
            - Sets entity attributes → Name, unique ID, device association, icon
            - Reads current distance setting → Initializes entity with saved user preference
            - Prepares for UI display → Sets up option formatting and current selection
        """
        self._entry = entry
        self._attr_name = "Distance Filter"
        self._attr_unique_id = f"{entry.entry_id}_distance_filter"
        self._attr_device_info = device_info
        # Read initial value from config entry data
        distance_filter = entry.data.get("distance_filter", DEFAULT_MAX_DISTANCE_KM)
        if distance_filter is None:
            self._attr_current_option = "No limit"
        else:
            # Convert to int to match format in DISTANCE_FILTER_OPTIONS (no decimal point)
            self._attr_current_option = str(int(distance_filter))
        self._attr_icon = "mdi:map-marker-radius"

    @property
    def options(self) -> list[str]:
        """Return available distance filter options with user-friendly km suffix for UI display.

        Provides the complete list of selectable distance options that users can choose
        from to filter concert events. The options are formatted for clear UI display
        with "km" units and include a "No limit" option for unlimited range.

        Option Processing:
        - Takes from DISTANCE_FILTER_OPTIONS → Predefined list of distance values
        - Adds "km" suffix → User-friendly unit display ("50 km", "100 km")
        - Preserves "No limit" → Special case without unit suffix
        - Maintains order → Options appear in logical sequence in UI

        Returns:
            Formatted distance options for select entity UI
            Example: ["25 km", "50 km", "100 km", "200 km", "No limit"]

        UI Integration:
            Used by Home Assistant to populate the select dropdown with available choices
            Options appear exactly as returned in the entity's selection interface
        """
        return [
            option + " km" if option != "No limit" else option
            for option in DISTANCE_FILTER_OPTIONS
        ]

    @property
    def current_option(self) -> str:
        """Return currently selected distance option with user-friendly km suffix for UI display.

        Provides the current distance filter selection in formatted form for display
        in the Home Assistant UI. Converts internal numeric values to user-friendly
        strings with proper unit suffixes.

        Format Conversion:
        - Internal "50" → Display "50 km"
        - Internal "No limit" → Display "No limit" (unchanged)
        - Handles None/empty → Returns "No limit" as fallback

        Returns:
            Formatted current selection for UI display
            Examples: "50 km", "100 km", "No limit"

        UI Integration:
            Used by Home Assistant to show current selection in select entity interface
            Value appears exactly as returned in the entity's current state display
        """
        if self._attr_current_option == "No limit" or not self._attr_current_option:
            return "No limit"
        return f"{self._attr_current_option} km"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional select entity attributes with descriptive information for UI display.

        Provides supplementary information about the distance filter entity that appears
        in the entity details panel, helping users understand the purpose and units
        of the distance filter setting.

        Attribute Content:
        - "description": Clear explanation of the distance filter's purpose and reference point
        - "unit": Current unit information ("kilometers" or None for "No limit")

        Unit Logic:
        - Shows "kilometers" when numeric distance selected → Clarifies measurement unit
        - Shows None when "No limit" selected → No unit needed for unlimited range

        Returns:
            Dictionary with descriptive attributes for entity details panel
            Includes description, unit depends on current selection

        UI Integration:
            - Entity details panel → Shows description and unit in entity information
            - Provides context → Users understand filter applies to distance from HA location
            - Dynamic unit display → Unit information updates when selection changes
        """
        return {
            "description": "Maximum distance from Home Assistant location to show concerts",
            "unit": "kilometers" if self.current_option != "No limit" else None,
        }

    async def async_select_option(self, option: str) -> None:
        """Handle user selection of new distance filter option with complete synchronization cascade.

        This method processes user selection changes from the UI, updating the config entry
        and triggering a complete refresh of the calendar event filtering system. The change
        takes immediate effect across all related entities.

        Selection Processing:
        1. Parse UI option → Strip "km" suffix to get internal numeric value
        2. Update internal state → Store new selection for entity display
        3. Update config entry → Persist new setting across restarts
        4. Refresh calendar cache → Recalculate event distances with new filter
        5. Update entity state → Trigger UI refresh to show new selection

        Synchronization Cascade:
        - Config entry update → Triggers config entry listeners across all platforms
        - Calendar cache refresh → update_filtered_calendar_cache() recalculates distances
        - Calendar entity update → Events re-filtered and displayed immediately
        - Entity state update → New selection appears in UI instantly

        Error Handling:
        - Invalid numeric conversion → Logs error and aborts operation
        - Preserves current state → No changes made if conversion fails

        Args:
            option: User-selected option from UI dropdown (e.g., "50 km", "No limit")

        Returns:
            None

        Side Effects:
            - Updates config entry → New distance setting persisted
            - Refreshes calendar cache → Events re-filtered by distance
            - Triggers UI updates → Calendar and select entity refresh immediately
            - Logs selection change → Debugging and monitoring purposes
        """
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
        """Get current distance filter value as numeric kilometers for programmatic use.

        Provides the current distance filter setting as a numeric value for use by
        other components that need to apply distance-based filtering. This method
        handles the conversion from display format to numeric processing format.

        Value Conversion:
        - "50 km" display → 50.0 numeric value
        - "No limit" display → None (unlimited range)
        - Invalid values → DEFAULT_MAX_DISTANCE_KM fallback with warning

        Error Handling:
        - Invalid numeric conversion → Logs warning and returns default
        - Missing values → Returns None for unlimited range
        - Preserves functionality → Always returns usable value

        Returns:
            float: Distance limit in kilometers for filtering calculations
            None: No distance limit (show all events regardless of distance)

        Used By:
            - calendar_utils.update_filtered_calendar_cache() → Applies distance filtering
            - Distance calculation functions → Determines which events to include
            - Other components needing programmatic access to distance setting

        Side Effects:
            - May log warning → When invalid distance values encountered
            - No state changes → Pure getter function for current setting
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
