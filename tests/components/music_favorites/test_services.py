"""Test Music Favorites service functionality."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.services import (
    ADD_FAVORITE_SCHEMA,
    REMOVE_FAVORITE_SCHEMA,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound, ServiceValidationError

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {"test-id": ["Test Band"]}},
        unique_id="music_favorites",
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_config_entry, mock_musicbrainz_client
):
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the integration
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


async def test_add_favorite_service_success(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test successful add_favorite service call."""
    with patch(
        "homeassistant.components.music_favorites.services.add_favorite"
    ) as mock_add:
        mock_add.return_value = None

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"name": "New Band", "type": "band"},
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][1] == setup_integration  # Second arg is config entry
        assert call_args[0][2] == "New Band"  # Third arg is name
        assert call_args[0][3] == "band"  # Fourth arg is type


async def test_remove_favorite_service_success(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test successful remove_favorite service call."""
    with patch(
        "homeassistant.components.music_favorites.services.remove_favorite"
    ) as mock_remove:
        mock_remove.return_value = None

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "remove_favorite",
            {"name": "Test Band"},
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][1] == setup_integration  # Second arg is config entry
        assert call_args[0][2] == "Test Band"  # Third arg is name


async def test_add_favorite_service_with_config_entry_id(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test add_favorite service with explicit config_entry parameter."""
    with patch(
        "homeassistant.components.music_favorites.services.add_favorite"
    ) as mock_add:
        mock_add.return_value = None

        # Call the service with explicit config entry ID
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {
                "config_entry": setup_integration.entry_id,
                "name": "Explicit Band",
                "type": "artist",
            },
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][2] == "Explicit Band"
        assert call_args[0][3] == "artist"


async def test_service_no_integration_found(hass: HomeAssistant) -> None:
    """Test service call when no integration is found."""
    # Don't set up any integration

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"name": "Test Band", "type": "band"},
            blocking=True,
        )


async def test_service_config_entry_not_found(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test service call with non-existent config entry ID."""
    with pytest.raises(ServiceValidationError, match="Config entry .* not found"):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"config_entry": "non_existent_id", "name": "Test Band", "type": "band"},
            blocking=True,
        )


async def test_service_config_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test service call when config entry is not loaded."""
    mock_config_entry.add_to_hass(hass)
    # Don't load the config entry (so services aren't registered)

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {
                "config_entry": mock_config_entry.entry_id,
                "name": "Test Band",
                "type": "band",
            },
            blocking=True,
        )


async def test_add_favorite_model_exception(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test add_favorite service when model function raises exception."""
    with patch(
        "homeassistant.components.music_favorites.services.add_favorite"
    ) as mock_add:
        mock_add.side_effect = ValueError("Duplicate favorite")

        # Service call should propagate the exception
        with pytest.raises(ValueError, match="Duplicate favorite"):
            await hass.services.async_call(
                DOMAIN,
                "add_favorite",
                {"name": "Duplicate Band", "type": "band"},
                blocking=True,
            )


async def test_remove_favorite_model_exception(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test remove_favorite service when model function raises exception."""
    with patch(
        "homeassistant.components.music_favorites.services.remove_favorite"
    ) as mock_remove:
        mock_remove.side_effect = ValueError("Favorite not found")

        # Service call should propagate the exception
        with pytest.raises(ValueError, match="Favorite not found"):
            await hass.services.async_call(
                DOMAIN,
                "remove_favorite",
                {"name": "Non-existent Band"},
                blocking=True,
            )


async def test_service_schema_validation_add_favorite() -> None:
    """Test that add_favorite service schema validation works."""

    # Valid data should pass
    valid_data = {"name": "Test Band", "type": "band"}
    result = ADD_FAVORITE_SCHEMA(valid_data)
    assert result == valid_data

    # Missing required field should fail
    with pytest.raises(vol.MultipleInvalid):
        ADD_FAVORITE_SCHEMA({"name": "Test Band"})  # Missing type

    # Invalid type should fail
    with pytest.raises(vol.MultipleInvalid):
        ADD_FAVORITE_SCHEMA({"name": "Test Band", "type": "invalid"})


async def test_service_schema_validation_remove_favorite() -> None:
    """Test that remove_favorite service schema validation works."""

    # Valid data should pass
    valid_data = {"name": "Test Band"}
    result = REMOVE_FAVORITE_SCHEMA(valid_data)
    assert result == valid_data

    # Missing required field should fail
    with pytest.raises(vol.MultipleInvalid):
        REMOVE_FAVORITE_SCHEMA({})  # Missing name


async def test_service_no_config_entries_after_setup(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test service call when integration loaded but no config entries exist."""
    # Integration is loaded (services registered), but we manually remove all config entries
    hass.config_entries._entries.clear()

    # Now the service exists, but our validation logic should fail
    with pytest.raises(
        ServiceValidationError, match="No Music Favorites integration found"
    ):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"name": "Test Band", "type": "band"},
            blocking=True,
        )


async def test_service_config_entry_not_loaded_after_setup(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test service call when config entry exists but is not loaded."""
    # Unload the config entry (services remain registered, but entry becomes NOT_LOADED)
    await hass.config_entries.async_unload(setup_integration.entry_id)

    # Now the service exists and config entry exists, but it's not loaded
    with pytest.raises(ServiceValidationError, match="Config entry .* is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {
                "config_entry": setup_integration.entry_id,
                "name": "Test Band",
                "type": "band",
            },
            blocking=True,
        )
