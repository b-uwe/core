"""The Music Favorites integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .models import add_favorite

_LOGGER = logging.getLogger(__name__)

# Service schema
ADD_FAVORITE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry"): str,
        vol.Required("name"): str,
        vol.Required("type"): vol.In(["band", "artist"]),
    }
)

_LOGGER.debug("Music Favorites module imported!")

# Very simple type...
type MusicFavoritesConfigEntry = ConfigEntry

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CONVERSATION]

# Make this integration be accessible from both UI as well as YAML
# TODO: Long term goal would be make YAML imported config immutable
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # YAML configuration schema:
                # TBD! For now, it just creates three arbitrary favorites
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _init_flow(hass: HomeAssistant) -> None:
    """Internal Helper function! Used to call the Config Flow Initialization from the YAML initialization."""
    try:
        await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
    except UnknownFlow:
        # Ignore the error, it doesn't matter
        _LOGGER.debug("Ignoring possible race condition when initializing Config Flow")


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up Music Favorites."""
    _LOGGER.debug("Setting up Music Favorites")

    async def add_favorite_service(call: ServiceCall) -> None:
        """Add a new favorite to the collection."""
        # If config_entry is provided, use it; otherwise find the first/only entry
        config_entry_id = call.data.get("config_entry")
        if config_entry_id:
            target_entry = hass.config_entries.async_get_entry(config_entry_id)
            if not target_entry:
                raise ServiceValidationError(
                    f"Config entry {config_entry_id} not found"
                )
        else:
            # For voice commands, auto-find the music_favorites entry
            entries = hass.config_entries.async_entries(DOMAIN)
            if not entries:
                raise ServiceValidationError("No Music Favorites integration found")
            target_entry = entries[0]  # Use the first (and typically only) entry

        if target_entry.state != ConfigEntryState.LOADED:
            raise ServiceValidationError(
                f"Config entry {target_entry.entry_id} is not loaded"
            )

        await add_favorite(
            hass,
            target_entry,
            call.data["name"],
            call.data["type"],
        )

    # Register the service
    _LOGGER.debug("Registering add_favorite service")
    hass.services.async_register(
        DOMAIN, "add_favorite", add_favorite_service, schema=ADD_FAVORITE_SCHEMA
    )

    # We are not registered in the Integrations list, hence we can only load via
    # configuration.yaml.
    # When this loads we create an instance of the service - but only ONCE, hence
    # the conditional
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    if not existing_entries:
        _LOGGER.debug(
            "Creating initial Music Favorites Service to be managed from UI from there on"
        )
        # We're artificially running the Config Flow here once
        hass.async_create_task(_init_flow(hass))

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Set up a Music Favorites Config Entry."""

    _LOGGER.debug("Setting up config entry: %s", entry.title)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
