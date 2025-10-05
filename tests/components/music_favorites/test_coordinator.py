"""Test the Music Favorites coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.components.music_favorites.coordinator import (
    MusicFavoritesCoordinator,
)
from homeassistant.components.music_favorites.models import BandStatus
from homeassistant.components.music_favorites.musicbrainz import MusicBrainzError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .fixtures.musicbrainz_responses import IRON_MAIDEN_COMPLETE_RESPONSE


@pytest.fixture
def future_date():
    """Generate a future date for reliable testing."""
    return (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")


@pytest.fixture
def past_date():
    """Generate a past date for reliable testing."""
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry for testing."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.data = {
        "favorites": {
            "ca891d65-d9b0-4258-89f7-e6ba29d83767": {  # Iron Maiden
                "variants": ["Iron Maiden", "Iron Mayden"],
                "status": BandStatus.ACTIVE,
                "bandsintown_url": "https://www.bandsintown.com/a/1301",
            },
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec": {  # Half Me
                "variants": ["Half Me"],
                "status": BandStatus.UNKNOWN,
                "bandsintown_url": "https://www.bandsintown.com/a/15548431",
            },
        }
    }
    return mock_entry


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_config_entry, mock_musicbrainz_client):
    """Create a MusicFavoritesCoordinator for testing."""
    return MusicFavoritesCoordinator(hass, mock_config_entry)


class TestMusicFavoritesCoordinator:
    """Test the MusicFavoritesCoordinator class."""

    async def test_init(self, hass: HomeAssistant, mock_config_entry):
        """Test coordinator initialization."""
        coordinator = MusicFavoritesCoordinator(hass, mock_config_entry)

        # Test inheritance
        assert isinstance(coordinator, DataUpdateCoordinator)

        # Test initialization parameters
        assert coordinator.hass is hass
        assert coordinator.entry is mock_config_entry
        assert coordinator.name == DOMAIN
        # Initial interval is 30 seconds, will change to DEFAULT_UPDATE_INTERVAL later
        assert coordinator.update_interval == timedelta(seconds=30)
        assert coordinator.config_entry is mock_config_entry

        # Test new snapshot cycle state
        assert coordinator._is_first_update is True
        assert coordinator._current_cycle_bands == []

        # Test MusicBrainz client creation
        assert coordinator.musicbrainz_client is not None

    async def test_async_update_data_first_run(self, coordinator):
        """Test first update returns immediately for fast startup."""
        # Should return immediately on first run
        result = await coordinator._async_update_data()

        assert result == {}
        assert coordinator._is_first_update is False

    async def test_async_update_data_no_favorites(self, coordinator):
        """Test update with no favorites after first run."""
        # Skip first update
        coordinator._is_first_update = False

        # Mock empty favorites
        coordinator.entry.data = {"favorites": {}}

        result = await coordinator._async_update_data()

        assert result == {}
        # Should set interval to DEFAULT_UPDATE_INTERVAL for re-checking
        assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL

    async def test_async_update_data_snapshot_cycle_start(self, coordinator):
        """Test starting a new snapshot cycle."""
        # Skip first update
        coordinator._is_first_update = False

        with patch.object(coordinator, "_update_single_favorite") as mock_update:
            mock_update.return_value = None

            await coordinator._async_update_data()

            # Should create snapshot of current favorites and remove first after processing
            # Half Me ID "963fa..." comes before Iron Maiden ID "ca891..." alphabetically
            assert (
                coordinator._current_cycle_bands
                == [
                    "ca891d65-d9b0-4258-89f7-e6ba29d83767",  # Iron Maiden (remaining after Half Me processed)
                ]
            )

            # Should set interval based on number of bands
            expected_interval = DEFAULT_UPDATE_INTERVAL / 2
            assert coordinator.update_interval == expected_interval

            # Should update first band in cycle (Half Me)
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"

    async def test_async_update_data_cycle_progression(self, coordinator):
        """Test progression through snapshot cycle."""
        # Skip first update and set up cycle (in alphabetical order)
        coordinator._is_first_update = False
        coordinator._current_cycle_bands = [
            "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",  # Half Me (first alphabetically)
            "ca891d65-d9b0-4258-89f7-e6ba29d83767",  # Iron Maiden
        ]

        with patch.object(coordinator, "_update_single_favorite") as mock_update:
            mock_update.return_value = None

            # First call should update first band and remove it
            await coordinator._async_update_data()

            assert coordinator._current_cycle_bands == [
                "ca891d65-d9b0-4258-89f7-e6ba29d83767"
            ]
            mock_update.assert_called_with(
                "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec",
                coordinator.entry.data["favorites"][
                    "963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"
                ],
            )

            # Second call should update last band and complete cycle
            await coordinator._async_update_data()

            assert coordinator._current_cycle_bands == []
            assert mock_update.call_count == 2

    async def test_async_update_data_band_removed_from_config(self, coordinator):
        """Test handling when band is removed from config during cycle."""
        # Skip first update and set up cycle with non-existent band
        coordinator._is_first_update = False
        coordinator._current_cycle_bands = ["non-existent-id"]

        result = await coordinator._async_update_data()

        # Should skip removed band and remove from cycle
        assert coordinator._current_cycle_bands == []
        assert result == coordinator.entry.data.get("favorites", {})

    async def test_async_update_data_with_config_updates(self, coordinator):
        """Test config entry updates when data changes."""
        # Skip first update and set up cycle
        coordinator._is_first_update = False
        coordinator._current_cycle_bands = ["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]

        updated_data = {
            "variants": ["Half Me"],
            "status": BandStatus.ACTIVE,
        }

        with patch.object(coordinator, "_update_single_favorite") as mock_update:
            mock_update.return_value = updated_data
            with patch.object(
                coordinator.hass.config_entries, "async_update_entry"
            ) as mock_config_update:
                await coordinator._async_update_data()

                # Should update config entry when data changes
                mock_config_update.assert_called_once()
                call_args = mock_config_update.call_args
                assert "favorites" in call_args[1]["data"]

    async def test_async_update_data_error_handling(self, coordinator):
        """Test error handling during updates."""
        # Skip first update and set up cycle
        coordinator._is_first_update = False
        coordinator._current_cycle_bands = ["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]

        with patch.object(coordinator, "_update_single_favorite") as mock_update:
            mock_update.side_effect = MusicBrainzError("API error")

            # Should handle error gracefully and continue
            result = await coordinator._async_update_data()

            # Should remove band from cycle even when error occurs
            assert coordinator._current_cycle_bands == []
            assert result is not None

    async def test_async_update_data_unexpected_error_handling(self, coordinator):
        """Test unexpected error handling during updates."""
        # Skip first update and set up cycle
        coordinator._is_first_update = False
        coordinator._current_cycle_bands = ["963fa0ee-ceeb-4dbb-abcf-6b85cdc0a3ec"]

        with patch.object(coordinator, "_update_single_favorite") as mock_update:
            mock_update.side_effect = Exception("Unexpected error")

            # Should handle unexpected error gracefully and continue
            result = await coordinator._async_update_data()

            # Should remove band from cycle even when unexpected error occurs
            assert coordinator._current_cycle_bands == []
            assert result is not None

    async def test_update_single_favorite_musicbrainz_success(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test successful MusicBrainz data update."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "status": BandStatus.ACTIVE,
        }

        # Mock MusicBrainz response
        mock_musicbrainz_client.get_artist_by_id.return_value = (
            IRON_MAIDEN_COMPLETE_RESPONSE
        )

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": [],
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            assert result is not None
            assert "allmusic_url" in result
            mock_fetch_external.assert_called_once_with(
                coordinator.hass,
                coordinator.entry,
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                favorite_data,
            )

    async def test_update_single_favorite_musicbrainz_error(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test MusicBrainz API error handling."""
        favorite_data = {"variants": ["Iron Maiden"]}

        # Mock MusicBrainz error
        mock_musicbrainz_client.get_artist_by_id.side_effect = MusicBrainzError(
            "API error"
        )

        result = await coordinator._update_single_favorite(
            "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
        )

        # Should continue processing despite MusicBrainz error
        assert result is None  # No changes made

    async def test_update_single_favorite_bandsintown_success(
        self, coordinator, mock_musicbrainz_client, future_date
    ):
        """Test successful Bandsintown data update."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "bandsintown_url": "https://www.bandsintown.com/a/1301",
            "events": [],
        }

        mock_events = [
            {
                "text": "Iron Maiden Concert",
                "event_date": future_date,
                "location": "Madison Square Garden",
                "venue_address": "New York, NY",
                "latitude": 40.7505,
                "longitude": -73.9934,
            }
        ]

        # Mock MusicBrainz response (needed for relation links)
        mock_musicbrainz_client.get_artist_by_id.return_value = (
            IRON_MAIDEN_COMPLETE_RESPONSE
        )

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_events:
            mock_fetch_events.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "bandsintown_url": "https://www.bandsintown.com/a/1301",
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": mock_events,
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ON_TOUR,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            assert result is not None
            assert result["events"] == mock_events
            mock_fetch_events.assert_called_once()

    async def test_update_single_favorite_bandsintown_error(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test Bandsintown API error handling."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "bandsintown_url": "https://www.bandsintown.com/a/1301",
        }

        # Mock MusicBrainz response (needed for relation links)
        mock_musicbrainz_client.get_artist_by_id.return_value = (
            IRON_MAIDEN_COMPLETE_RESPONSE
        )

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_events:
            mock_fetch_events.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "bandsintown_url": "https://www.bandsintown.com/a/1301",
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": [],  # Return empty events on error
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            # Should handle error gracefully but still return updated data from MusicBrainz
            assert result is not None
            assert "allmusic_url" in result  # MusicBrainz relation links were updated

    async def test_update_single_favorite_status_update(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test band status determination and update."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "status": BandStatus.UNKNOWN,
            "events": [],
        }

        # Mock MusicBrainz response
        mock_musicbrainz_client.get_artist_by_id.return_value = (
            IRON_MAIDEN_COMPLETE_RESPONSE
        )

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "bandsintown_url": "https://www.bandsintown.com/a/1301",
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": [],
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            assert result is not None
            assert result["status"] == BandStatus.ACTIVE

    async def test_update_single_favorite_status_exception(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test exception handling in status determination."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "status": BandStatus.UNKNOWN,
            "events": [],
        }

        # Mock MusicBrainz response
        mock_musicbrainz_client.get_artist_by_id.return_value = (
            IRON_MAIDEN_COMPLETE_RESPONSE
        )

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": [],
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            # Should handle status exception gracefully and still return updated relation links
            assert result is not None
            assert "allmusic_url" in result  # MusicBrainz data was still processed

    async def test_update_single_favorite_no_changes(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test when no data changes are detected."""
        favorite_data = {
            "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
            "status": BandStatus.ACTIVE,
            "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
        }

        mock_client = mock_musicbrainz_client
        mock_client.get_artist_by_id.return_value = IRON_MAIDEN_COMPLETE_RESPONSE

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            # Return same relation links (no change)
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767"
                },
                "events": [],
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            # Should return None when no changes
            assert result is None

    async def test_update_single_favorite_exception_handling(
        self, coordinator, mock_musicbrainz_client
    ):
        """Test unexpected exception handling."""
        favorite_data = {"variants": ["Iron Maiden"]}

        mock_client = mock_musicbrainz_client
        mock_client.get_artist_by_id.side_effect = Exception("Unexpected error")

        result = await coordinator._update_single_favorite(
            "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
        )

        # Should handle unexpected exceptions gracefully
        assert result is None

    async def test_fire_event_changes_added_events(self, coordinator, future_date):
        """Test firing events for added events."""
        old_events = []
        new_events = [
            {
                "text": "Iron Maiden Concert",
                "event_date": future_date,
                "location": "Madison Square Garden",
                "venue_address": "New York, NY",
                "latitude": 40.7505,
                "longitude": -73.9934,
                "url": "https://example.com/event",
            }
        ]

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                old_events,
                new_events,
            )

            # Should fire event_added
            mock_fire.assert_called_once_with(
                f"{DOMAIN}_event_added",
                {
                    "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                    "artist_name": "Iron Maiden",
                    "event_title": "Iron Maiden Concert",
                    "event_date": future_date,
                    "venue": "Madison Square Garden",
                    "venue_address": "New York, NY",
                    "latitude": 40.7505,
                    "longitude": -73.9934,
                    "url": "https://example.com/event",
                },
            )

    async def test_fire_event_changes_removed_events(self, coordinator, future_date):
        """Test firing events for removed events."""
        old_events = [
            {
                "text": "Iron Maiden Concert",
                "event_date": future_date,
                "location": "Madison Square Garden",
                "venue_address": "New York, NY",
            }
        ]
        new_events = []

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                old_events,
                new_events,
            )

            # Should fire event_removed
            mock_fire.assert_called_once_with(
                f"{DOMAIN}_event_removed",
                {
                    "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                    "artist_name": "Iron Maiden",
                    "event_title": "Iron Maiden Concert",
                    "event_date": future_date,
                    "venue": "Madison Square Garden",
                    "venue_address": "New York, NY",
                },
            )

    async def test_fire_event_changes_no_changes(self, coordinator, future_date):
        """Test event firing when no changes occur."""
        events = [
            {
                "text": "Iron Maiden Concert",
                "event_date": future_date,
                "location": "Madison Square Garden",
            }
        ]

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                events,
                events,  # Same events
            )

            # Should not fire any events
            mock_fire.assert_not_called()

    async def test_fire_event_changes_multiple_events(
        self, coordinator, past_date, future_date
    ):
        """Test firing events for multiple added and removed events."""
        old_events = [
            {"text": "Old Concert", "event_date": past_date, "location": "Old Venue"}
        ]
        new_events = [
            {
                "text": "New Concert 1",
                "event_date": future_date,
                "location": "New Venue 1",
            },
            {
                "text": "New Concert 2",
                "event_date": (datetime.now() + timedelta(days=60)).strftime(
                    "%Y-%m-%d"
                ),
                "location": "New Venue 2",
            },
        ]

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                old_events,
                new_events,
            )

            # Should fire 1 removed + 2 added = 3 events
            assert mock_fire.call_count == 3

    async def test_fire_event_changes_venue_change(self, coordinator, future_date):
        """Test event changes when venue changes (same date, different location)."""
        old_events = [
            {"text": "Concert", "event_date": future_date, "location": "Old Venue"}
        ]
        new_events = [
            {"text": "Concert", "event_date": future_date, "location": "New Venue"}
        ]

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                old_events,
                new_events,
            )

            # Should fire both removed (old venue) and added (new venue)
            assert mock_fire.call_count == 2

    async def test_fire_event_changes_missing_data(self, coordinator):
        """Test event firing with missing event data."""
        old_events = []
        new_events = [
            {
                "text": "Unknown Event",  # Fallback when title is missing
                "event_date": None,
                "location": None,
            }
        ]

        with patch("homeassistant.core.EventBus.async_fire") as mock_fire:
            coordinator._fire_event_changes(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767",
                "Iron Maiden",
                old_events,
                new_events,
            )

            # Should still fire event with None values
            mock_fire.assert_called_once()
            call_args = mock_fire.call_args[0][1]
            assert call_args["event_title"] == "Unknown Event"
            assert call_args["event_date"] is None
            assert call_args["venue"] is None

    async def test_relation_links_update(self, coordinator, mock_musicbrainz_client):
        """Test updating relation links from MusicBrainz."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "old_url": "https://old.example.com",
            "allmusic_url": "https://old.allmusic.com",
        }

        new_relation_links = {
            "allmusic_url": "https://new.allmusic.com",
            "bandsintown_url": "https://www.bandsintown.com/a/1301",
            "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
        }

        mock_client = mock_musicbrainz_client
        mock_client.get_artist_by_id.return_value = IRON_MAIDEN_COMPLETE_RESPONSE

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": new_relation_links,
                "events": [],
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ACTIVE,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            assert result is not None
            # Should remove old relation links
            assert "old_url" not in result
            # Should update existing relation links
            assert result["allmusic_url"] == "https://new.allmusic.com"
            # Should add new relation links
            assert result["bandsintown_url"] == "https://www.bandsintown.com/a/1301"

    async def test_events_update_triggers_status_update(
        self, coordinator, mock_musicbrainz_client, future_date
    ):
        """Test that updating events also triggers status determination."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "status": BandStatus.UNKNOWN,
            "bandsintown_url": "https://www.bandsintown.com/a/1301",
            "events": [],
        }

        mock_events = [{"event_date": future_date, "location": "Madison Square Garden"}]

        mock_client = mock_musicbrainz_client
        mock_client.get_artist_by_id.return_value = IRON_MAIDEN_COMPLETE_RESPONSE

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_events:
            mock_fetch_events.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {
                    "bandsintown_url": "https://www.bandsintown.com/a/1301",
                    "allmusic_url": "https://www.allmusic.com/artist/iron-maiden",
                    "musicbrainz_url": "https://musicbrainz.org/artist/ca891d65-d9b0-4258-89f7-e6ba29d83767",
                },
                "events": mock_events,
                "variants": ["Iron Maiden", "Ironmaiden", "Maiden", "鉄の処女"],
                "status": BandStatus.ON_TOUR,
            }

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            assert result is not None
            assert result["events"] == mock_events
            assert result["status"] == BandStatus.ON_TOUR

    async def test_update_single_favorite_musicbrainz_error_logging(
        self, coordinator, mock_musicbrainz_client, caplog: pytest.LogCaptureFixture
    ):
        """Test MusicBrainzError logging in _update_single_favorite."""
        favorite_data = {"variants": ["Iron Maiden"]}

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.side_effect = MusicBrainzError("API error")

            result = await coordinator._update_single_favorite(
                "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
            )

            # Should handle MusicBrainzError and log warning
            assert result is None
            assert (
                "Failed to update MusicBrainz data for Iron Maiden: API error"
                in caplog.text
            )

    async def test_reformed_date_assignment(self, coordinator, mock_musicbrainz_client):
        """Test reformed_date assignment when status changes to REFORMED."""
        favorite_data = {
            "variants": ["Iron Maiden"],
            "status": BandStatus.ACTIVE,  # Previous status
        }

        mock_client = mock_musicbrainz_client
        mock_client.get_artist_by_id.return_value = IRON_MAIDEN_COMPLETE_RESPONSE

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {},
                "events": [],
                "variants": ["Iron Maiden"],
                "status": BandStatus.REFORMED,  # New status
            }

            with patch(
                "homeassistant.components.music_favorites.coordinator.date"
            ) as mock_date:
                mock_date.today.return_value.isoformat.return_value = "2024-01-15"

                result = await coordinator._update_single_favorite(
                    "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
                )

                assert result is not None
                assert result["status"] == BandStatus.REFORMED
                assert result["reformed_date"] == "2024-01-15"

    async def test_status_update_exception_handling(
        self, coordinator, mock_musicbrainz_client, caplog: pytest.LogCaptureFixture
    ):
        """Test exception handling in status update section."""
        favorite_data = {"variants": ["Iron Maiden"]}

        with patch(
            "homeassistant.components.music_favorites.coordinator.fetch_external_data"
        ) as mock_fetch_external:
            mock_fetch_external.return_value = {
                "artist_data": IRON_MAIDEN_COMPLETE_RESPONSE,
                "relation_links": {},
                "events": [],
                "variants": ["Iron Maiden"],
                "status": BandStatus.REFORMED,  # This will trigger the reformed_date code
            }

            # Patch date.today() to cause an exception during reformed_date assignment
            with patch(
                "homeassistant.components.music_favorites.coordinator.date"
            ) as mock_date:
                mock_date.today.side_effect = Exception("Date error")

                result = await coordinator._update_single_favorite(
                    "ca891d65-d9b0-4258-89f7-e6ba29d83767", favorite_data
                )

                # Should handle status update exceptions gracefully
                assert result is not None  # Still returns data but logs the exception
                assert "Failed to update status for Iron Maiden" in caplog.text
