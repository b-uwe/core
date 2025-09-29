"""Test Music Favorites select platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.music_favorites.const import (
    DEFAULT_MAX_DISTANCE_KM,
    DISTANCE_FILTER_OPTIONS,
    DOMAIN,
)
from homeassistant.components.music_favorites.select import (
    DistanceFilterSelect,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry for testing."""
    return MockConfigEntry(
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


@pytest.fixture
def mock_device_info():
    """Create mock device info."""
    return DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
    )


async def test_async_setup_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setting up select entities."""
    mock_add_entities = MagicMock()

    with patch(
        "homeassistant.components.music_favorites.select.create_calendar_device_info"
    ) as mock_device_info:
        mock_device_info.return_value = DeviceInfo(
            identifiers={(DOMAIN, "test_device")},
            name="Test Device",
        )

        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

        # Verify that async_add_entities was called with one entity
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], DistanceFilterSelect)


def test_distance_filter_select_init_default_value(
    mock_config_entry, mock_device_info
) -> None:
    """Test DistanceFilterSelect initialization with default distance_filter."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)

    # Check attributes
    assert entity._attr_name == "Distance Filter"
    assert entity._attr_unique_id == f"{mock_config_entry.entry_id}_distance_filter"
    assert entity._attr_device_info == mock_device_info
    assert entity.options == [
        option + " km" if option != "No limit" else option
        for option in DISTANCE_FILTER_OPTIONS
    ]
    assert entity._attr_current_option == "100"  # From mock config entry
    assert entity._attr_icon == "mdi:map-marker-radius"
    assert entity._attr_has_entity_name is True


def test_distance_filter_select_init_no_limit() -> None:
    """Test DistanceFilterSelect initialization with no distance limit."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {},
            "distance_filter": None,  # No limit
        },
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    assert entity._attr_current_option == "No limit"


def test_distance_filter_select_init_missing_distance_filter() -> None:
    """Test DistanceFilterSelect initialization with missing distance_filter key."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},  # No distance_filter key
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    # Should default to DEFAULT_MAX_DISTANCE_KM
    assert entity._attr_current_option == str(DEFAULT_MAX_DISTANCE_KM)


def test_extra_state_attributes_with_limit(mock_config_entry, mock_device_info) -> None:
    """Test extra state attributes with distance limit."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)

    attributes = entity.extra_state_attributes
    assert attributes is not None
    assert (
        attributes["description"]
        == "Maximum distance from Home Assistant location to show concerts"
    )
    assert attributes["unit"] == "kilometers"


def test_extra_state_attributes_no_limit() -> None:
    """Test extra state attributes with no distance limit."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {},
            "distance_filter": None,  # No limit
        },
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    attributes = entity.extra_state_attributes
    assert attributes is not None
    assert (
        attributes["description"]
        == "Maximum distance from Home Assistant location to show concerts"
    )
    assert attributes["unit"] is None


async def test_async_select_option_numeric_value(
    hass: HomeAssistant, mock_config_entry, mock_device_info
) -> None:
    """Test selecting a numeric distance filter option."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)
    entity.hass = hass

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.select.update_filtered_calendar_cache"
        ) as mock_update_cache,
        patch.object(entity, "async_write_ha_state") as mock_write_state,
    ):
        await entity.async_select_option("50")

        # Check that the current option was updated
        assert entity._attr_current_option == "50"

        # Verify config entry was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_entry = call_args[0][0]  # First argument (the entry)
        updated_data = call_args[1]["data"]  # The data keyword argument

        assert updated_entry == mock_config_entry
        assert updated_data["distance_filter"] == 50.0

        # Verify cache was updated
        mock_update_cache.assert_called_once_with(hass, mock_config_entry)

        # Verify state was written
        mock_write_state.assert_called_once()


async def test_async_select_option_no_limit(
    hass: HomeAssistant, mock_config_entry, mock_device_info
) -> None:
    """Test selecting 'No limit' option."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)
    entity.hass = hass

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.select.update_filtered_calendar_cache"
        ) as mock_update_cache,
        patch.object(entity, "async_write_ha_state") as mock_write_state,
    ):
        await entity.async_select_option("No limit")

        # Check that the current option was updated
        assert entity._attr_current_option == "No limit"

        # Verify config entry was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        updated_data = call_args[1]["data"]

        assert updated_data["distance_filter"] is None

        # Verify cache was updated
        mock_update_cache.assert_called_once_with(hass, mock_config_entry)

        # Verify state was written
        mock_write_state.assert_called_once()


async def test_async_select_option_invalid_value(
    hass: HomeAssistant,
    mock_config_entry,
    mock_device_info,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test selecting an invalid distance filter option."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)
    entity.hass = hass

    with (
        patch.object(hass.config_entries, "async_update_entry") as mock_update,
        patch(
            "homeassistant.components.music_favorites.select.update_filtered_calendar_cache"
        ) as mock_update_cache,
    ):
        await entity.async_select_option("invalid")

        # Should log error and return early without updating anything
        assert "Invalid distance filter option: invalid" in caplog.text

        # Config entry should NOT be updated
        mock_update.assert_not_called()
        mock_update_cache.assert_not_called()


def test_get_distance_limit_km_numeric_value(
    mock_config_entry, mock_device_info
) -> None:
    """Test get_distance_limit_km with numeric value."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)

    limit = entity.get_distance_limit_km()
    assert limit == 100.0


def test_get_distance_limit_km_no_limit() -> None:
    """Test get_distance_limit_km with 'No limit' option."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={
            "favorites": {},
            "distance_filter": None,
        },
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    limit = entity.get_distance_limit_km()
    assert limit is None


def test_get_distance_limit_km_invalid_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test get_distance_limit_km with invalid value."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    # Simulate invalid current option
    entity._attr_current_option = "invalid"

    limit = entity.get_distance_limit_km()

    # Should log warning and return default
    assert "Invalid distance filter value: invalid km, using default" in caplog.text
    assert limit == float(DEFAULT_MAX_DISTANCE_KM)


def test_get_distance_limit_km_empty_value() -> None:
    """Test get_distance_limit_km with empty value."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites_unique_id",
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, "test_device")},
        name="Test Device",
    )

    entity = DistanceFilterSelect(config_entry, device_info)

    # Simulate empty current option
    entity._attr_current_option = ""

    limit = entity.get_distance_limit_km()
    assert limit is None


async def test_async_select_option_state_write(
    hass: HomeAssistant, mock_config_entry, mock_device_info
) -> None:
    """Test that async_select_option calls async_write_ha_state."""
    entity = DistanceFilterSelect(mock_config_entry, mock_device_info)
    entity.hass = hass

    # Mock the async_write_ha_state method
    with (
        patch.object(hass.config_entries, "async_update_entry"),
        patch(
            "homeassistant.components.music_favorites.select.update_filtered_calendar_cache"
        ),
        patch.object(entity, "async_write_ha_state") as mock_write_state,
    ):
        await entity.async_select_option("25")

        # Verify state was written
        mock_write_state.assert_called_once()


def test_distance_filter_options_constant() -> None:
    """Test that DISTANCE_FILTER_OPTIONS contains expected values."""
    expected_options = ["25", "50", "100", "200", "500", "No limit"]
    assert expected_options == DISTANCE_FILTER_OPTIONS


def test_default_max_distance_constant() -> None:
    """Test DEFAULT_MAX_DISTANCE_KM constant value."""
    assert DEFAULT_MAX_DISTANCE_KM == 100
