"""Test Music Favorites service functionality."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.music_favorites.const import DOMAIN
from homeassistant.components.music_favorites.services import (
    ADD_FAVORITE_SCHEMA,
    REMOVE_FAVORITE_SCHEMA,
    _get_target_entry,
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
        data={"favorites": {"test-id": {"variants": ["Test Band"]}}},
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
            {
                "musicbrainz_id": "17b53d9f-5db6-4f6a-808a-0769e99b5111",
            },
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][1] == setup_integration  # Second arg is config entry
        assert (
            call_args[0][2] == "17b53d9f-5db6-4f6a-808a-0769e99b5111"
        )  # Third arg is musicbrainz_id


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
            {"musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767"},
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][1] == setup_integration  # Second arg is config entry
        assert (
            call_args[0][2] == "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )  # Third arg is musicbrainz_id


async def test_add_favorite_service_auto_discovery(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test add_favorite service with auto-discovery of single config entry."""
    with patch(
        "homeassistant.components.music_favorites.services.add_favorite"
    ) as mock_add:
        mock_add.return_value = None

        # Call the service - config entry is auto-discovered (single-instance integration)
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {
                "musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767",
            },
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][1] == setup_integration  # Second arg is config entry
        assert (
            call_args[0][2] == "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )  # Third arg is musicbrainz_id


async def test_service_no_integration_found(hass: HomeAssistant) -> None:
    """Test service call when no integration is found."""
    # Don't set up any integration

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {"musicbrainz_id": "0383dadf-2a4e-4d10-a46a-e9e041da8eb3"},
            blocking=True,
        )


async def test_service_remove_favorite_simple(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test simple remove_favorite service call without config_entry parameter."""
    with patch(
        "homeassistant.components.music_favorites.services.remove_favorite"
    ) as mock_remove:
        mock_remove.return_value = None

        await hass.services.async_call(
            DOMAIN,
            "remove_favorite",
            {"musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767"},
            blocking=True,
        )

        # Verify the model function was called correctly
        mock_remove.assert_called_once()
        call_args = mock_remove.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert (
            call_args[0][1] == setup_integration
        )  # Second arg is config entry (auto-discovered)
        assert (
            call_args[0][2] == "ca891d65-d9b0-4258-89f7-e6ba29d83767"
        )  # Third arg is musicbrainz_id


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
                "musicbrainz_id": "66c662b6-6e2f-4930-8610-912e24c63ed1",
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
                {
                    "musicbrainz_id": "5b11f4ce-a62d-471e-81fc-a69a8278c7da",
                },
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
                {"musicbrainz_id": "00000000-0000-0000-0000-000000000000"},
                blocking=True,
            )


async def test_service_schema_validation_add_favorite() -> None:
    """Test that add_favorite service schema validation works."""

    # Valid data should pass
    valid_data = {
        "musicbrainz_id": "678d88b2-87b0-403b-b63d-5da7465aecc3",
    }
    result = ADD_FAVORITE_SCHEMA(valid_data)
    assert result == valid_data

    # Missing required field should fail
    with pytest.raises(vol.MultipleInvalid):
        ADD_FAVORITE_SCHEMA({})  # Missing musicbrainz_id


async def test_service_schema_validation_remove_favorite() -> None:
    """Test that remove_favorite service schema validation works."""

    # Valid data should pass
    valid_data = {"musicbrainz_id": "ca891d65-d9b0-4258-89f7-e6ba29d83767"}
    result = REMOVE_FAVORITE_SCHEMA(valid_data)
    assert result == valid_data

    # Missing required field should fail
    with pytest.raises(vol.MultipleInvalid):
        REMOVE_FAVORITE_SCHEMA({})  # Missing musicbrainz_id


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
            {
                "musicbrainz_id": "83d91898-7763-47d7-b03b-b92132375c47",
            },
            blocking=True,
        )


async def test_service_config_entry_not_loaded_after_setup(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test service call when config entry exists but is not loaded."""
    # Unload the config entry (services remain registered, but entry becomes NOT_LOADED)
    await hass.config_entries.async_unload(setup_integration.entry_id)

    # Now the service exists and config entry exists, but it's not loaded
    with pytest.raises(
        ServiceValidationError, match="Music Favorites integration is not loaded"
    ):
        await hass.services.async_call(
            DOMAIN,
            "add_favorite",
            {
                "musicbrainz_id": "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d",
            },
            blocking=True,
        )


async def test_get_target_entry_no_integration(hass: HomeAssistant) -> None:
    """Test _get_target_entry when no Music Favorites integration exists."""
    # Don't set up any config entry

    # This should raise a ServiceValidationError
    with pytest.raises(
        ServiceValidationError, match="No Music Favorites integration found"
    ):
        _get_target_entry(hass)
