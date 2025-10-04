"""Test Music Favorites integration setup and teardown."""
# All tests are currently Claude Code-written, which needs to change, apparently
# But for now, that's much better than me fiddling with a thing I don't understand

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.components.music_favorites import _init_import_flow, async_setup
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.musicbrainz import MusicBrainzError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of a config entry."""
    # Import and patch the actual import location in __init__.py

    with patch(
        "homeassistant.components.music_favorites.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.search_artists.return_value = [
            {"id": "test", "name": "Test", "disambiguation": "", "score": 100}
        ]

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Music Favorites",
            data={
                "favorites": {
                    "test-id": {
                        "variants": ["Test Band"],
                        "status": "Active",
                        "events": [],
                    }
                },
                "distance_filter": 100,
            },
            unique_id="music_favorites_unique_id",
        )
        entry.add_to_hass(hass)

        # Test the actual setup with mocked MusicBrainz
        result = await hass.config_entries.async_setup(entry.entry_id)

        assert result is True
        assert entry.state is ConfigEntryState.LOADED

        # Verify MusicBrainz was called
        mock_client.search_artists.assert_called_once()

        # Verify runtime_data is set up correctly
        assert entry.runtime_data is not None
        assert "update_interval" in entry.runtime_data
        assert "musicbrainz_client" in entry.runtime_data


async def test_unload_entry_success(
    hass: HomeAssistant, mock_musicbrainz_client
) -> None:
    """Test successful unloading of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {
                "test-id": {"variants": ["Test Band"], "status": "Active", "events": []}
            },
            "distance_filter": 100,
        },
        unique_id="music_favorites_unique_id",
    )
    entry.add_to_hass(hass)

    # First set up the entry
    setup_result = await hass.config_entries.async_setup(entry.entry_id)
    assert setup_result is True

    # Check state after setup
    setup_state = entry.state
    assert setup_state is ConfigEntryState.LOADED

    # Now test unloading
    unload_result = await hass.config_entries.async_unload(entry.entry_id)
    assert unload_result is True

    # Check state after unload (in separate variable)
    unload_state = entry.state
    assert unload_state is ConfigEntryState.NOT_LOADED


async def test_service_registration(hass: HomeAssistant) -> None:
    """Test that services are properly registered during integration setup."""
    result = await async_setup(hass, {})

    assert result is True

    # Verify both services were registered by checking they exist
    assert hass.services.has_service(DOMAIN, "add_favorite")
    assert hass.services.has_service(DOMAIN, "remove_favorite")


async def test_singleton_behavior(hass: HomeAssistant, mock_musicbrainz_client) -> None:
    """Test that only one config entry can exist (singleton pattern)."""
    # First config flow should succeed
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] == "create_entry"
    assert result1["title"] == "Music Favorites"

    # Second attempt should be aborted (singleton enforcement)
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"

    # Verify only one config entry exists
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "music_favorites"


async def test_runtime_data_structure(
    hass: HomeAssistant, mock_musicbrainz_client
) -> None:
    """Test that runtime_data is properly structured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {
                "test-id": {"variants": ["Test Band"], "status": "Active", "events": []}
            },
            "distance_filter": 100,
        },
        unique_id="music_favorites_unique_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    assert result is True
    assert entry.state is ConfigEntryState.LOADED

    # Check runtime_data structure
    assert entry.runtime_data is not None
    assert isinstance(entry.runtime_data, dict)
    assert "update_interval" in entry.runtime_data
    assert "musicbrainz_client" in entry.runtime_data
    assert "filtered_calendar_events" in entry.runtime_data

    # Verify it's actually a timedelta
    assert isinstance(entry.runtime_data["update_interval"], timedelta)

    # Verify filtered events cache is a list
    assert isinstance(entry.runtime_data["filtered_calendar_events"], list)


async def test_init_import_flow_unknown_flow_exception(hass: HomeAssistant) -> None:
    """Test _init_import_flow handles UnknownFlow exception gracefully."""
    with patch.object(hass.config_entries.flow, "async_init", side_effect=UnknownFlow):
        # This should not raise an exception - it should catch and log
        await _init_import_flow(hass)


async def test_setup_entry_musicbrainz_error(hass: HomeAssistant) -> None:
    """Test setup entry with MusicBrainzError raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.music_favorites.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.search_artists.side_effect = MusicBrainzError("API unavailable")

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Music Favorites",
            data={
                "favorites": {
                    "test-id": {
                        "variants": ["Test Band"],
                        "status": "Active",
                        "events": [],
                    }
                },
                "distance_filter": 100,
            },
            unique_id="music_favorites_unique_id",
        )
        entry.add_to_hass(hass)

        # Setup should return False and set state to SETUP_RETRY
        # because ConfigEntryNotReady triggers Home Assistant's retry logic
        result = await hass.config_entries.async_setup(entry.entry_id)
        assert result is False
        assert entry.state is ConfigEntryState.SETUP_RETRY
