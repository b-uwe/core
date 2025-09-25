"""Test Music Favorites integration setup and teardown."""

from datetime import timedelta

from homeassistant.components.music_favorites import async_setup
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {"test-id": ["Test Band"]}},
        unique_id="music_favorites_unique_id",
    )
    entry.add_to_hass(hass)

    # Test the actual setup - no mocking needed for basic success case
    result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.state is ConfigEntryState.LOADED

    # Verify runtime_data is set up correctly
    assert entry.runtime_data is not None
    assert "update_interval" in entry.runtime_data


async def test_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unloading of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {"test-id": ["Test Band"]}},
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


async def test_singleton_behavior(hass: HomeAssistant) -> None:
    """Test that only one config entry can exist (singleton pattern)."""
    # First config flow should succeed
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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


async def test_runtime_data_structure(hass: HomeAssistant) -> None:
    """Test that runtime_data is properly structured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {"test-id": ["Test Band"]}},
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

    # Verify it's actually a timedelta
    assert isinstance(entry.runtime_data["update_interval"], timedelta)
    assert entry.runtime_data["update_interval"] == timedelta(hours=6)
