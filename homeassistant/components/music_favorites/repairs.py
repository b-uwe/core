"""Repair flows for the Music Favorites integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .musicbrainz import MusicBrainzClient, MusicBrainzError

_LOGGER = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow to fix the specified issue."""

    if issue_id == "musicbrainz_connectivity":
        repair_flow: RepairsFlow = MusicBrainzConnectivityRepairFlow()
        repair_flow.issue_id = issue_id
        repair_flow.data = data
        return repair_flow

    # For any other issues, use a simple confirmation flow
    confirm_flow: RepairsFlow = ConfirmRepairFlow()
    confirm_flow.issue_id = issue_id
    confirm_flow.data = data
    return confirm_flow


class MusicBrainzConnectivityRepairFlow(RepairsFlow):
    """Handler for MusicBrainz connectivity repair flow."""

    def __init__(self) -> None:
        """Initialize repair flow."""
        super().__init__()
        self._test_result: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial repair step."""
        data = self.data or {}
        return self.async_show_menu(
            step_id="init",
            menu_options=["test_connection", "ignore_issue"],
            description_placeholders={
                "issue_details": str(data.get("error", "Unknown error"))
            },
        )

    async def async_step_test_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Test MusicBrainz connectivity."""
        if user_input is not None:
            # User clicked "Test Connection", now actually test it
            try:
                client = MusicBrainzClient(self.hass)
                await client.search_artists("test", limit=1)

                # Success! Mark as fixed
                self._test_result = "success"
                return await self.async_step_test_result()

            except MusicBrainzError as err:
                # Still failing
                self._test_result = "failed"
                data = self.data or {}
                data["current_error"] = str(err)
                self.data = data
                return await self.async_step_test_result()

            except Exception as err:  # noqa: BLE001
                # Unexpected error - broad catch is needed for repair flows
                # to handle any unforeseen connectivity issues gracefully
                self._test_result = "unexpected_error"
                data = self.data or {}
                data["current_error"] = str(err)
                self.data = data
                return await self.async_step_test_result()

        # Show the test form
        return self.async_show_form(
            step_id="test_connection",
            data_schema=vol.Schema({}),
            description_placeholders={
                "note": "This will test if MusicBrainz is reachable from your Home Assistant instance."
            },
        )

    async def async_step_test_result(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show test results and next steps."""
        if self._test_result == "success":
            # Connection works now - mark issue as fixed
            return self.async_create_entry(
                title="MusicBrainz connectivity restored", data={}
            )

        if self._test_result == "failed":
            # Still failing - show troubleshooting options
            data = self.data or {}
            return self.async_show_menu(
                step_id="test_result",
                menu_options=["retry_test", "check_network", "ignore_issue"],
                description_placeholders={
                    "error": str(data.get("current_error", "Connection failed")),
                    "suggestions": (
                        "• Check your internet connection\n"
                        "• Verify MusicBrainz.org is accessible\n"
                        "• Check firewall settings\n"
                        "• Wait and try again later"
                    ),
                },
            )

        # unexpected_error
        # Show generic error message
        data = self.data or {}
        return self.async_show_form(
            step_id="test_result",
            data_schema=vol.Schema({}),
            description_placeholders={
                "error": str(data.get("current_error", "Unexpected error")),
                "suggestion": "Please check the Home Assistant logs for more details.",
            },
            last_step=True,
        )

    async def async_step_retry_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Retry the connection test."""
        return await self.async_step_test_connection(user_input)

    async def async_step_check_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show network troubleshooting information."""
        return self.async_show_form(
            step_id="check_network",
            data_schema=vol.Schema({}),
            description_placeholders={
                "steps": (
                    "1. Check your internet connection is working\n"
                    "2. Try visiting musicbrainz.org in a web browser\n"
                    "3. Check if your firewall blocks outgoing connections\n"
                    "4. If behind a corporate firewall, contact your IT department\n"
                    "5. The MusicBrainz service might be temporarily down"
                )
            },
            last_step=True,
        )

    async def async_step_ignore_issue(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ignore the connectivity issue."""
        return self.async_create_entry(
            title="MusicBrainz connectivity issue ignored", data={"ignored": True}
        )
