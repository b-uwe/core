"""Test Music Favorites diagnostics functionality."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_musicbrainz_client,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(
        domain="music_favorites",
        title="Music Favorites",
        data={
            "favorites": {
                "test-id-1": ["Test Band", "TB"],
                "test-id-2": ["Solo Artist"],
            }
        },
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    # Verify config entry info
    assert result["config_entry"]["title"] == "Music Favorites"
    assert result["config_entry"]["entry_id"] == entry.entry_id
    assert result["config_entry"]["domain"] == "music_favorites"

    # Verify favorites statistics
    stats = result["favorites_statistics"]
    assert stats["total_favorites"] == 2
    assert stats["favorites_with_variants"] == 1  # Only test-id-1 has variants
    assert stats["average_variants_per_favorite"] == 1.5  # (2+1)/2

    # Verify favorites data
    favorites = result["favorites_data"]
    assert "test-id-1" in favorites
    assert "test-id-2" in favorites

    # Check first favorite with variants
    favorite1 = favorites["test-id-1"]
    assert favorite1["display_name"] == "Test Band"
    assert favorite1["variant_count"] == 1
    assert favorite1["variants"] == ["TB"]

    # Check second favorite without variants
    favorite2 = favorites["test-id-2"]
    assert favorite2["display_name"] == "Solo Artist"
    assert favorite2["variant_count"] == 0
    assert favorite2["variants"] == []

    # Entity states may or may not be present (depends on entity setup timing)
    assert "entity_states" in result


async def test_entry_diagnostics_no_favorites(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_musicbrainz_client,
) -> None:
    """Test config entry diagnostics with no favorites."""
    entry = MockConfigEntry(
        domain="music_favorites",
        title="Empty Music Favorites",
        data={"favorites": {}},
        unique_id="music_favorites_empty",
    )
    entry.add_to_hass(hass)

    # Set up the integration
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    # Verify statistics for empty favorites
    stats = result["favorites_statistics"]
    assert stats["total_favorites"] == 0
    assert stats["favorites_with_variants"] == 0
    assert stats["average_variants_per_favorite"] == 0

    # Verify empty favorites data
    assert result["favorites_data"] == {}
    assert result["entity_states"] == {}


async def test_entry_diagnostics_with_entity_states(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_musicbrainz_client,
) -> None:
    """Test config entry diagnostics that includes entity states."""
    entry = MockConfigEntry(
        domain="music_favorites",
        title="Music Favorites",
        data={
            "favorites": {
                "test-id-1": ["Test Band", "TB"],
                "test-id-2": ["Solo Artist"],
            }
        },
        unique_id="music_favorites",
    )
    entry.add_to_hass(hass)

    # Set up the integration and wait for entities to be created
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Create a mock entity state for one of the favorites
    # This will trigger the entity_states logic in diagnostics
    entity_registry = er.async_get(hass)

    # Register a sensor entity for test-id-1
    entity_registry.async_get_or_create(
        "sensor",
        "music_favorites",
        "music_favorites_favorite_test-id-1",
        suggested_object_id="test_band_favorite",
    )

    # Set a state for this entity
    hass.states.async_set(
        "sensor.test_band_favorite",
        "tracked",
        {
            "musicbrainz_id": "test-id-1",
            "display_name": "Test Band",
            "variant_count": 1,
            "variants": ["TB"],
        },
    )

    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    # Verify that entity states are now included
    entity_states = result["entity_states"]
    assert "Test Band" in entity_states

    # Verify the entity state data
    test_band_state = entity_states["Test Band"]
    assert test_band_state["state"] == "tracked"
    assert test_band_state["attributes"]["musicbrainz_id"] == "test-id-1"
    assert test_band_state["attributes"]["display_name"] == "Test Band"
