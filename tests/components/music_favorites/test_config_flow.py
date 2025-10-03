"""Test the Music Favorites config flow."""

from collections.abc import Mapping
from typing import Any

from homeassistant import config_entries
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _assert_default_favorites_structure(result_data: Mapping[str, Any]) -> None:
    """Assert that the favorites structure is initialized with default data."""
    favorites = result_data["favorites"]

    # Check that favorites dict exists and has a default entry
    assert isinstance(favorites, dict)
    assert len(favorites) == 1


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    # First step shows form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit form to test connectivity and create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Should create entry after connectivity test passes
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Favorites"
    assert "favorites" in result["data"]

    # Verify favorites structure is configured with default data
    _assert_default_favorites_structure(result["data"])


async def test_user_flow_duplicate_prevented(hass: HomeAssistant) -> None:
    """Test that duplicate config entries are prevented."""
    # Create first entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_default_favorites_structure(result1["data"])

    # Try to create second entry - should be aborted immediately (unique ID check)
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

    # Import flow should create entry directly (no form for YAML)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Favorites"
    assert "favorites" in result["data"]

    # Verify favorites structure is configured with default data
    _assert_default_favorites_structure(result["data"])


async def test_import_flow_duplicate_prevented(hass: HomeAssistant) -> None:
    """Test that duplicate imports are prevented."""
    # Create entry via user flow
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_default_favorites_structure(result1["data"])

    # Try import - should be aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
