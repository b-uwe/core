"""Test the Music Favorites config flow."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.musicbrainz import MusicBrainzError
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _assert_empty_favorites_structure(result_data: Mapping[str, Any]) -> None:
    """Assert that the favorites structure is initialized but empty."""
    favorites = result_data["favorites"]

    # Check that favorites dict exists but is empty (no default bands)
    assert isinstance(favorites, dict)
    assert len(favorites) == 0


async def test_user_flow_success(hass: HomeAssistant, mock_musicbrainz_client) -> None:
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

    # Verify MusicBrainz connectivity was tested (called in both config flow and setup)
    assert mock_musicbrainz_client.search_artists.call_count >= 1

    # Verify favorites structure is configured (but empty)
    _assert_empty_favorites_structure(result["data"])


async def test_user_flow_duplicate_prevented(
    hass: HomeAssistant, mock_musicbrainz_client
) -> None:
    """Test that duplicate config entries are prevented."""
    # Create first entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_empty_favorites_structure(result1["data"])

    # Try to create second entry - should be aborted immediately (unique ID check)
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant, mock_musicbrainz_client) -> None:
    """Test import flow from YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    # Import forwards to user flow
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Complete the flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Music Favorites"
    assert "favorites" in result["data"]

    # Verify favorites structure is configured (but empty)
    _assert_empty_favorites_structure(result["data"])


async def test_import_flow_duplicate_prevented(
    hass: HomeAssistant, mock_musicbrainz_client
) -> None:
    """Test that duplicate imports are prevented."""
    # Create entry via user flow
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    _assert_empty_favorites_structure(result1["data"])

    # Try import - should be aborted
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_user_flow_connection_error(hass: HomeAssistant) -> None:
    """Test config flow with MusicBrainz connection error."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        # Mock connection failure
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client
        mock_client.search_artists.side_effect = MusicBrainzError("Connection failed")

        # Start config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        # Submit form - should show error
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Should show form with error
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "cannot_connect"
        assert result["description_placeholders"] is not None
        assert (
            "MusicBrainz API returned an error"
            in result["description_placeholders"]["note"]
        )


async def test_user_flow_client_error(hass: HomeAssistant) -> None:
    """Test config flow with generic client error."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client
        mock_client.search_artists.side_effect = aiohttp.ClientError("HTTP error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_connector_error(hass: HomeAssistant) -> None:
    """Test config flow with connection error (DNS, network unreachable, etc.)."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client

        # Create a ClientConnectorError that can be logged properly
        class MockConnectorError(aiohttp.ClientConnectorError):
            def __str__(self):
                return "Cannot connect to host musicbrainz.org:443"

        # Create instance without calling parent __init__ to avoid required parameters
        connector_error = MockConnectorError.__new__(MockConnectorError)
        mock_client.search_artists.side_effect = connector_error

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_timeout_error(hass: HomeAssistant) -> None:
    """Test config flow with timeout error."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client
        mock_client.search_artists.side_effect = TimeoutError("Request timed out")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "timeout"


async def test_user_flow_generic_exception(hass: HomeAssistant) -> None:
    """Test config flow with unexpected exception."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client
        mock_client.search_artists.side_effect = ValueError("Unexpected error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "unknown"


async def test_user_flow_retry_after_error(hass: HomeAssistant) -> None:
    """Test config flow retry after connection error."""
    with (
        patch(
            "homeassistant.components.music_favorites.musicbrainz.MusicBrainzClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.music_favorites.config_flow.MusicBrainzClient"
        ) as mock_client_class_config,
        patch(
            "homeassistant.components.music_favorites.MusicBrainzClient"
        ) as mock_client_class_init,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client_class_config.return_value = mock_client
        mock_client_class_init.return_value = mock_client

        # First call fails, second succeeds
        mock_client.search_artists.side_effect = [
            MusicBrainzError("Connection failed"),
            [{"id": "test", "name": "Test", "disambiguation": "", "score": 100}],
        ]

        # Start config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # First submission fails
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "cannot_connect"

        # Retry - should succeed
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Music Favorites"
