"""Data update coordinator for the Music Favorites integration."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .bandsintown import extract_music_events
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .datatypes import MusicFavoritesConfigEntry
from .ldjson import LdJsonError, fetch_and_extract_ldjson
from .models import BandStatus, determine_band_status, extract_pure_event_data
from .musicbrainz import MusicBrainzClient, MusicBrainzError, extract_relation_links

_LOGGER = logging.getLogger(__name__)


class MusicFavoritesCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for updating music favorites data from external APIs.

    This coordinator implements an update strategy that balances concurrent API usage
    with data freshness. It uses a snapshot-based cycle approach to update one favorite
    at a time, distributing updates evenly over the default interval.

    Update Strategy:
    - Takes snapshot of favorites at cycle start → Ensures consistency during updates
    - Updates one favorite per cycle → Spreads API load and respects rate limits
    - Dynamic interval calculation → Distributes updates evenly over 6-hour period
    - Handles favorite additions/removals → Adjusts schedule automatically

    Synchronization Points:
    - Config entry updates → Updates propagate to all platforms automatically
    - Entity state changes → Triggers UI refreshes via async_write_ha_state()
    - Event changes → Fires custom HA events for added/removed concerts
    - Calendar cache updates → Refreshes calendar entity with new event data
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MusicFavoritesConfigEntry,
    ) -> None:
        """Initialize the coordinator with update scheduling and state tracking.

        Sets up the data update coordinator with a cycle-based update logic
        that processes one favorite at a time to distribute API load evenly over time
        while ensuring all favorites stay current with external data sources.

        Coordinator Architecture:
        - Initial fast startup → Set a 30-second first interval, but else return immediately to avoid blocking HA startup
        - Dynamic interval calculation → Distributes updates over DEFAULT_UPDATE_INTERVAL
        - Snapshot-based cycles → Takes consistent view of favorites at cycle start
        - API rate limiting → Updates one favorite per cycle to respect external APIs

        State Management:
        - Tracks current cycle state → Knows which favorites still need updates
        - First update flag → Enables fast startup behavior
        - MusicBrainz client → Handles artist data and relation URL fetching

        Args:
            hass: Home Assistant instance for config entry management and event firing
            entry: Config entry containing favorites data and serving as central data store

        Returns:
            None

        Side Effects:
            - Initializes DataUpdateCoordinator with fast startup interval
            - Creates MusicBrainz client for external API communication
            - Sets up internal state tracking for cycle-based updates
        """
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=30  # Those 30 seconds are for the VERY FIRST call!
            ),
            config_entry=entry,
        )
        self.entry = entry
        self.musicbrainz_client = MusicBrainzClient(hass)
        self._is_first_update = True
        self._current_cycle_bands: list[str] = []

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch updated data for favorites using intelligent snapshot cycle approach.

        This method implements an update strategy that processes one favorite
        per call, distributing API load over time while ensuring all favorites stay current.

        Update Cycle Logic:
        1. Fast startup → Return empty dict on first call to avoid blocking HA startup
        2. Check cycle state → Start new cycle if current cycle is complete
        3. Calculate dynamic interval → Distribute updates evenly over DEFAULT_UPDATE_INTERVAL
        4. Process a favorite → Update one favorite with fresh data from APIs
        5. Update config entry → Trigger synchronization across all platforms

        Synchronization Triggers:
        - Config entry update → All platforms receive notifications via update listeners
        - Entity state changes → Sensors refresh with new status/events data
        - Event changes → Custom HA events fired for added/removed concerts
        - Return updated data → Coordinator notifies any registered listeners

        Returns:
            dict: Current favorites data from config entry

            HA's DataUpdateCoordinator automatically stores this returned data in coordinator.data
            and notifies any registered coordinator listeners, but our integration doesn't use
            coordinator.data. Our entities read from entry.data instead for architectural consistency.

            Real Data Flow in Our Integration:
            1. Coordinator updates a favorite → Updates entry.data via async_update_entry()
            2. Config entry update → Triggers config entry listeners across all platforms
            3. Entities refresh → Read fresh data from entry.data, not coordinator.data

            We return actual data (not None/{}) for forward compatibility and HA interface compliance.

        Side Effects:
            - May update config entry data → Triggers platform synchronization
            - May fire HA events for event changes → External automations can listen
            - Adjusts update interval dynamically → Balances freshness vs. API usage
        """
        _LOGGER.debug("Starting music favorites data update cycle")

        # Fast startup: return immediately on first run to avoid blocking HA startup
        if self._is_first_update:
            _LOGGER.debug("Update Coordinator initialized 1st time")
            self._is_first_update = False
            return {}

        # Check if we need to start a new cycle (current cycle complete)
        if not self._current_cycle_bands:
            # Take snapshot of current favorites for new cycle
            current_favorites = dict(self.entry.data.get("favorites", {}))
            if not current_favorites:
                # No favorites to update: Set interval to DEFAULT_UPDATE_INTERVAL
                # to re-check later
                self.update_interval = DEFAULT_UPDATE_INTERVAL
                _LOGGER.debug(
                    "No favorites to update, will re-check in %s",
                    DEFAULT_UPDATE_INTERVAL,
                )
                return {}

            # Create sorted list for predictable ordering
            self._current_cycle_bands = sorted(current_favorites.keys())
            total_bands = len(self._current_cycle_bands)

            # Calculate interval: distribute evenly across DEFAULT_UPDATE_INTERVAL
            new_interval = DEFAULT_UPDATE_INTERVAL / total_bands
            self.update_interval = new_interval

            _LOGGER.debug(
                "Starting new update cycle with %d bands, update interval: %s",
                total_bands,
                new_interval,
            )

        # Update the next band in the current cycle
        if self._current_cycle_bands:
            # Get the first band from current cycle
            musicbrainz_id = self._current_cycle_bands[0]

            # Get current data for this band
            current_favorites = dict(self.entry.data.get("favorites", {}))
            if musicbrainz_id not in current_favorites:
                # Band was removed from config, skip and remove from cycle
                _LOGGER.debug("%s no longer in favorite acts, skipping", musicbrainz_id)
                self._current_cycle_bands.pop(0)
                return dict(current_favorites)

            favorite_data = current_favorites[musicbrainz_id]
            favorite_name = favorite_data.get("variants", ["Unknown"])[0]

            _LOGGER.debug(
                "Updating band %s (%d remaining in cycle)",
                favorite_name,
                len(self._current_cycle_bands),
            )

            try:
                updated_data = await self._update_single_favorite(
                    musicbrainz_id, favorite_data
                )

                if updated_data:
                    _LOGGER.debug("Updated data for favorite %s", favorite_name)

                    # Fetch fresh config entry data and update
                    fresh_entry_data = self.entry.data
                    fresh_favorites = dict(fresh_entry_data.get("favorites", {}))
                    fresh_favorites[musicbrainz_id] = updated_data

                    # Update config entry with fresh data
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={**fresh_entry_data, "favorites": fresh_favorites},
                    )

            except (MusicBrainzError, LdJsonError) as err:
                _LOGGER.warning(
                    "Failed to update favorite %s (%s): %s",
                    musicbrainz_id,
                    favorite_name,
                    err,
                )
            except Exception:
                _LOGGER.exception(
                    "Unexpected error updating favorite %s (%s)",
                    musicbrainz_id,
                    favorite_name,
                )

            # Remove the updated band from current cycle (whether successful or not)
            self._current_cycle_bands.pop(0)

        # Return current favorites data
        return dict(self.entry.data.get("favorites", {}))

    async def _update_single_favorite(
        self,
        musicbrainz_id: str,
        current_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update data for a single favorite by fetching fresh information from external APIs.

        This method orchestrates the complete data refresh process for one favorite,
        fetching updates from MusicBrainz and Bandsintown APIs in sequence. It implements
        some change detection to avoid unnecessary config entry updates.

        Multi-API Update Process:
        1. Fetch MusicBrainz artist data → Update relation URLs (bandsintown_url, allmusic_url, etc.)
        2. Fetch Bandsintown events → Update upcoming concert information
        3. Determine band status → Calculate status based on life-span and events
        4. Change detection → Only return data if any information actually changed

        API Error Handling:
        - MusicBrainz failures → Log warning, continue with events update
        - Bandsintown failures → Log warning, continue with status update
        - Unexpected errors → Log exception, continue processing other steps

        Synchronization Points:
        - Returns updated data → Triggers config entry update in calling _async_update_data()
        - Config entry update → Triggers all platform listeners for UI refresh
        - Event changes → Fires custom HA events via _fire_event_changes()

        Args:
            musicbrainz_id: Unique MusicBrainz identifier for the artist to update
            current_data: Current favorite data from config entry for change comparison

        Returns:
            dict: Updated favorite data if any changes detected, triggers config entry sync
            None: No changes detected, prevents unnecessary config entry updates

        Side Effects:
            - May fire HA events for event changes → External automations can listen
            - Logs API successes/failures → Debugging and monitoring information
            - No direct UI updates → Updates happen via config entry changes in caller
        """
        favorite_name = current_data.get("variants", ["Unknown"])[0]
        updated_data = current_data.copy()
        data_changed = False
        artist_data = None

        # Step 1: Update MusicBrainz data (artist info, relations)
        try:
            _LOGGER.debug("Fetching MusicBrainz data for %s", favorite_name)
            artist_data = await self.musicbrainz_client.get_artist_by_id(musicbrainz_id)

            # Update relation links
            new_relation_links = extract_relation_links(artist_data)
            current_relation_links = {
                k: v for k, v in current_data.items() if k.endswith("_url")
            }

            if new_relation_links != current_relation_links:
                # Remove old relation links and add new ones
                for key in list(updated_data.keys()):
                    if key.endswith("_url"):
                        del updated_data[key]
                updated_data.update(new_relation_links)
                # Always add musicbrainz_url (constructed from ID)
                updated_data["musicbrainz_url"] = (
                    f"https://musicbrainz.org/artist/{musicbrainz_id}"
                )
                data_changed = True
                _LOGGER.debug("Updated relation links for %s", favorite_name)

        except MusicBrainzError as err:
            _LOGGER.warning(
                "Failed to update MusicBrainz data for %s: %s", favorite_name, err
            )
        except Exception:
            _LOGGER.exception(
                "Unexpected error fetching MusicBrainz data for %s", favorite_name
            )

        # Step 2: Update Bandsintown events data if we have a Bandsintown URL
        bandsintown_url = updated_data.get("bandsintown_url")
        if bandsintown_url:
            try:
                _LOGGER.debug("Fetching Bandsintown data for %s", favorite_name)
                ldjson_data = await fetch_and_extract_ldjson(self.hass, bandsintown_url)
                music_events = extract_music_events(ldjson_data)

                if music_events:
                    # Extract pure date and time data for storage
                    new_events_data = extract_pure_event_data(music_events)
                    current_events = current_data.get("events", [])

                    if new_events_data != current_events:
                        updated_data["events"] = new_events_data
                        data_changed = True
                        _LOGGER.debug(
                            "Updated %d events for %s",
                            len(new_events_data),
                            favorite_name,
                        )

                        # Fire individual events for each change
                        self._fire_event_changes(
                            musicbrainz_id,
                            favorite_name,
                            current_events,
                            new_events_data,
                        )

            except LdJsonError as err:
                _LOGGER.warning(
                    "Failed to update Bandsintown events for %s: %s", favorite_name, err
                )

        # Step 3: Update band status
        if artist_data:
            try:
                current_status = current_data.get("status")
                events_data = updated_data.get("events", [])
                previous_artist_data = current_data.get("previous_artist_data")
                reformed_date = current_data.get("reformed_date")

                new_status = determine_band_status(
                    artist_data,
                    events_data,
                    current_status,
                    previous_artist_data,
                    reformed_date,
                )

                if new_status != current_status:
                    updated_data["status"] = new_status
                    data_changed = True

                    # Store reformed_date when status changes to REFORMED
                    if (
                        new_status == BandStatus.REFORMED
                        and current_status != BandStatus.REFORMED
                    ):
                        updated_data["reformed_date"] = date.today().isoformat()

                    _LOGGER.debug(
                        "Updated status for %s: %s -> %s",
                        favorite_name,
                        current_status,
                        new_status,
                    )

                # Always store current artist data as previous for next comparison
                updated_data["previous_artist_data"] = artist_data

            except Exception:
                _LOGGER.exception("Failed to update status for %s", favorite_name)

        return updated_data if data_changed else None

    def _fire_event_changes(
        self,
        musicbrainz_id: str,
        artist_name: str,
        old_events: list[dict[str, Any]],
        new_events: list[dict[str, Any]],
    ) -> None:
        """Fire Home Assistant events for new and removed events.

        This method detects and announces concert event changes via the HA event bus,
        enabling external automations and notifications to respond to new or cancelled concerts.

        Event Detection Logic:
        1. Create unique keys for each event (date + location)
        2. Compare old vs new event sets to find additions and removals
        3. Fire custom HA events with detailed event information

        Custom Events Fired:
        - "music_favorites_event_added" → New concert announced
        - "music_favorites_event_removed" → Concert cancelled/removed

        External Integration:
        These events can be used in HA automations for notifications, calendar updates,
        or integration with other systems when favorite artists announce new shows.

        Args:
            musicbrainz_id: MusicBrainz ID of the artist (for event data)
            artist_name: Display name of the artist (for user-friendly event data)
            old_events: Previous events list (before coordinator update)
            new_events: Current events list (after coordinator update)

        Returns:
            None

        Side Effects:
            - Fires custom HA events → Available for automations and external listeners
            - Logs event changes → Debugging and monitoring purposes
        """

        # Create event keys for comparison (event_date + location)
        def event_key(event: dict[str, Any]) -> tuple[str | None, str | None]:
            return (event.get("event_date"), event.get("location"))

        # Build sets of event keys for comparison
        old_keys = {event_key(event) for event in old_events}
        new_keys = {event_key(event) for event in new_events}

        # Find added and removed events! I like how you subtract sets 😅👏
        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys

        # Fire events for added events
        for event in new_events:
            if event_key(event) in added_keys:
                event_data = {
                    "musicbrainz_id": musicbrainz_id,
                    "artist_name": artist_name,
                    "event_title": event.get("text", "Unknown Event"),
                    "event_date": event.get("event_date"),
                    "venue": event.get("location"),
                    "venue_address": event.get("venue_address"),
                    "latitude": event.get("latitude"),
                    "longitude": event.get("longitude"),
                    "url": event.get("url"),
                }
                self.hass.bus.async_fire(f"{DOMAIN}_event_added", event_data)
                _LOGGER.debug(
                    "Fired event_added for %s: %s on %s",
                    artist_name,
                    event.get("text"),
                    event.get("event_date"),
                )

        # Fire events for removed events
        for event in old_events:
            if event_key(event) in removed_keys:
                event_data = {
                    "musicbrainz_id": musicbrainz_id,
                    "artist_name": artist_name,
                    "event_title": event.get("text", "Unknown Event"),
                    "event_date": event.get("event_date"),
                    "venue": event.get("location"),
                    "venue_address": event.get("venue_address"),
                }
                self.hass.bus.async_fire(f"{DOMAIN}_event_removed", event_data)
                _LOGGER.debug(
                    "Fired event_removed for %s: %s on %s",
                    artist_name,
                    event.get("text"),
                    event.get("event_date"),
                )
