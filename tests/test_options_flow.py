"""Tests for the export options flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_MODE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component

from . import setup_config_entry
from .const import MOCK_CONFIG_DATA

if TYPE_CHECKING:
    from home_disconnect.testutils import MockAppliance
    from homeassistant.core import HomeAssistant


async def test_options_flow_shows_export_menu(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """The options flow shows a mode selector on init."""
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_export_safe_creates_download_link_notification(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """
    Safe export closes the flow and notifies with a plain, admin-gated download link.

    No signed path or expiry - the download view itself is gated by
    @require_admin (see export_view.py), matching HA core's own
    DownloadDiagnosticsView instead of the old signed-link approach.
    """
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with (
        patch(
            "custom_components.homeconnect_ws.config_flow.get_url",
            return_value="http://homeassistant.local:8123",
        ),
        patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock) as mock_call,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"mode": "safe"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_call.assert_awaited_once()
    call_args = mock_call.call_args
    assert call_args.args[0] == "persistent_notification"
    assert call_args.args[1] == "create"
    message = call_args.args[2]["message"]
    assert f"/api/homeconnect_ws/export/{entry.entry_id}/safe" in message
    assert "authSig=" not in message
    assert "fake_brand_Fake_vib_profile_safe.zip" in message


async def test_options_flow_export_full_creates_download_link_notification(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """Full export also notifies with a plain, admin-gated link - no more filesystem write."""
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, {**MOCK_CONFIG_DATA, CONF_MODE: "AES"})
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with (
        patch(
            "custom_components.homeconnect_ws.config_flow.get_url",
            return_value="http://homeassistant.local:8123",
        ),
        patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock) as mock_call,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"mode": "full"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_call.assert_awaited_once()
    message = mock_call.call_args.args[2]["message"]
    assert f"/api/homeconnect_ws/export/{entry.entry_id}/full" in message
    assert "authSig=" not in message
    assert "fake_brand_Fake_vib_profile_full.zip" in message


async def test_options_flow_export_matches_current_request_url(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """
    The download link matches how the current browser is connected, not just the internal URL.

    get_url()'s default prefers the internal URL even when the request
    submitting this form came in over a remote/Nabu Casa connection, which
    produces an unreachable link (#73). require_current_request=True is what
    makes get_url() match the actual connection instead.
    """
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with (
        patch(
            "custom_components.homeconnect_ws.config_flow.get_url",
            return_value="https://example.ui.nabu.casa",
        ) as mock_get_url,
        patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock),
    ):
        await hass.config_entries.options.async_configure(result["flow_id"], {"mode": "safe"})

    mock_get_url.assert_called_once_with(hass, require_current_request=True)


async def test_options_flow_export_falls_back_without_current_request(
    hass: HomeAssistant,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """Falls back to the plain URL lookup if there's no active HTTP request to match."""
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, MOCK_CONFIG_DATA)
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    result = await hass.config_entries.options.async_init(entry.entry_id)

    with (
        patch(
            "custom_components.homeconnect_ws.config_flow.get_url",
            side_effect=[NoURLAvailableError, "http://homeassistant.local:8123"],
        ) as mock_get_url,
        patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock) as mock_call,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"mode": "safe"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_get_url.call_count == 2
    message = mock_call.call_args.args[2]["message"]
    assert "http://homeassistant.local:8123" in message
