"""Test the Music Favorites config flow."""

from collections.abc import Mapping
from typing import Any

from homeassistant import config_entries
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _assert_default_bands_present(result_data: Mapping[str, Any]) -> None:
    """Assert that the default pre-configured bands are present."""
    favorites = result_data["favorites"]

    # Check that all three default bands are present
    assert "f0d05c64-9959-4ae1-899b-acf51b97638c" in favorites  # Dyscarnate
    assert "f9b57146-c5ce-41ad-adfb-ee904a4f7b19" in favorites  # Misery Index
    assert "ab81255c-7a4f-4528-bb77-4a3fbd8e8317" in favorites  # Jungle Rot

    # Verify at least one band name is correct
    assert favorites["f0d05c64-9959-4ae1-899b-acf51b97638c"] == ["Dyscarnate"]


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow - creates entry immediately."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should immediately create entry (no form needed)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Favorites"
    assert "favorites" in result["data"]

    # Verify default bands are configured
    _assert_default_bands_present(result["data"])


async def test_user_flow_duplicate_prevented(hass: HomeAssistant) -> None:
    """Test that duplicate config entries are prevented."""
    # Create first entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_default_bands_present(result1["data"])

    # Try to create second entry - should be aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test import flow from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    # Should create entry immediately (same as user flow)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Favorites"
    assert "favorites" in result["data"]

    # Verify default bands are configured
    _assert_default_bands_present(result["data"])


async def test_import_flow_duplicate_prevented(hass: HomeAssistant) -> None:
    """Test that duplicate imports are prevented."""
    # Create entry via user flow
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_default_bands_present(result1["data"])

    # Try import - should be aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
