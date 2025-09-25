"""The Music Favorites integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import register_services
from .types import MusicFavoritesConfigEntry

_LOGGER = logging.getLogger(__name__)


_LOGGER.debug("Music Favorites module imported!")


_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CONVERSATION]

# Make this integration be accessible from both UI as well as YAML
# TO DO: Long term goal would be make YAML imported config immutable
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

    # Register all services
    register_services(hass)

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

    # Initialize runtime data dict
    entry.runtime_data = {
        "update_interval": timedelta(hours=6),
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MusicFavoritesConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
