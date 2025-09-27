"""Test Music Favorites repair flows."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.music_favorites.musicbrainz import MusicBrainzError
from homeassistant.components.music_favorites.repairs import (
    MusicBrainzConnectivityRepairFlow,
    async_create_fix_flow,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_async_create_fix_flow_musicbrainz_connectivity(
    hass: HomeAssistant,
) -> None:
    """Test creating repair flow for MusicBrainz connectivity issue."""
    flow = await async_create_fix_flow(
        hass, "musicbrainz_connectivity", {"error": "Connection timeout"}
    )

    assert isinstance(flow, MusicBrainzConnectivityRepairFlow)
    assert flow.issue_id == "musicbrainz_connectivity"
    assert flow.data == {"error": "Connection timeout"}


async def test_async_create_fix_flow_other_issue(hass: HomeAssistant) -> None:
    """Test creating repair flow for other issues."""
    flow = await async_create_fix_flow(hass, "other_issue", {"some": "data"})

    assert isinstance(flow, ConfirmRepairFlow)
    assert flow.issue_id == "other_issue"
    assert flow.data == {"some": "data"}


async def test_musicbrainz_repair_flow_init_step(hass: HomeAssistant) -> None:
    """Test the initial step of MusicBrainz repair flow."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow.issue_id = "musicbrainz_connectivity"
    flow.data = {"error": "Connection failed"}

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert "test_connection" in result["menu_options"]
    assert "ignore_issue" in result["menu_options"]
    assert result["description_placeholders"] is not None
    assert result["description_placeholders"]["issue_details"] == "Connection failed"


async def test_musicbrainz_repair_flow_init_step_no_data(hass: HomeAssistant) -> None:
    """Test the initial step with no data."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow.issue_id = "musicbrainz_connectivity"
    flow.data = None

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    assert result["description_placeholders"] is not None
    assert result["description_placeholders"]["issue_details"] == "Unknown error"


async def test_musicbrainz_repair_flow_test_connection_form(
    hass: HomeAssistant,
) -> None:
    """Test showing the test connection form."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass

    result = await flow.async_step_test_connection()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "test_connection"
    assert result["description_placeholders"] is not None
    assert "note" in result["description_placeholders"]


async def test_musicbrainz_repair_flow_test_connection_success(
    hass: HomeAssistant,
) -> None:
    """Test successful connection test."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.music_favorites.repairs.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(return_value=[{"name": "Test"}])

        result = await flow.async_step_test_connection({"test": True})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "MusicBrainz connectivity restored"
        assert flow._test_result == "success"


async def test_musicbrainz_repair_flow_test_connection_musicbrainz_error(
    hass: HomeAssistant,
) -> None:
    """Test connection test with MusicBrainz error."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow.data = {}

    with patch(
        "homeassistant.components.music_favorites.repairs.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(
            side_effect=MusicBrainzError("API timeout")
        )

        result = await flow.async_step_test_connection({"test": True})

        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "test_result"
        assert "retry_test" in result["menu_options"]
        assert "check_network" in result["menu_options"]
        assert "ignore_issue" in result["menu_options"]
        assert flow._test_result == "failed"
        assert flow.data["current_error"] == "API timeout"


async def test_musicbrainz_repair_flow_test_connection_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test connection test with unexpected error."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow.data = {}

    with patch(
        "homeassistant.components.music_favorites.repairs.MusicBrainzClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.search_artists = AsyncMock(side_effect=ValueError("Unexpected"))

        result = await flow.async_step_test_connection({"test": True})

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "test_result"
        assert result["last_step"] is True
        assert flow._test_result == "unexpected_error"
        assert flow.data["current_error"] == "Unexpected"


async def test_musicbrainz_repair_flow_test_result_success(hass: HomeAssistant) -> None:
    """Test test result step with success."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow._test_result = "success"

    result = await flow.async_step_test_result()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "MusicBrainz connectivity restored"


async def test_musicbrainz_repair_flow_test_result_failed(hass: HomeAssistant) -> None:
    """Test test result step with failure."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow._test_result = "failed"
    flow.data = {"current_error": "Connection timeout"}

    result = await flow.async_step_test_result()

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "test_result"
    assert "retry_test" in result["menu_options"]
    assert "check_network" in result["menu_options"]
    assert "ignore_issue" in result["menu_options"]
    assert result["description_placeholders"] is not None
    assert "Connection timeout" in result["description_placeholders"]["error"]


async def test_musicbrainz_repair_flow_test_result_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test test result step with unexpected error."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow._test_result = "unexpected_error"
    flow.data = {"current_error": "Something went wrong"}

    result = await flow.async_step_test_result()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "test_result"
    assert result["last_step"] is True
    assert result["description_placeholders"] is not None
    assert "Something went wrong" in result["description_placeholders"]["error"]


async def test_musicbrainz_repair_flow_test_result_no_data(hass: HomeAssistant) -> None:
    """Test test result step with no data."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass
    flow._test_result = "failed"
    flow.data = None

    result = await flow.async_step_test_result()

    assert result["type"] == FlowResultType.MENU
    assert result["description_placeholders"] is not None
    assert "Connection failed" in result["description_placeholders"]["error"]


async def test_musicbrainz_repair_flow_retry_test(hass: HomeAssistant) -> None:
    """Test retry test step."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass

    with patch.object(flow, "async_step_test_connection") as mock_test:
        mock_test.return_value = {"type": FlowResultType.FORM}

        result = await flow.async_step_retry_test({"retry": True})

        mock_test.assert_called_once_with({"retry": True})
        assert result["type"] == FlowResultType.FORM


async def test_musicbrainz_repair_flow_check_network(hass: HomeAssistant) -> None:
    """Test check network step."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass

    result = await flow.async_step_check_network()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "check_network"
    assert result["last_step"] is True
    assert (
        result["description_placeholders"] is not None
        and "Check your internet connection"
        in result["description_placeholders"]["steps"]
    )


async def test_musicbrainz_repair_flow_ignore_issue(hass: HomeAssistant) -> None:
    """Test ignore issue step."""
    flow = MusicBrainzConnectivityRepairFlow()
    flow.hass = hass

    result = await flow.async_step_ignore_issue()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "MusicBrainz connectivity issue ignored"
    assert result["data"] == {"ignored": True}


async def test_musicbrainz_repair_flow_initialization() -> None:
    """Test MusicBrainzConnectivityRepairFlow initialization."""
    flow = MusicBrainzConnectivityRepairFlow()

    assert flow._test_result is None
