"""Tests for the profile export HTTP view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.homeconnect_ws.export_view import HCExportView
from homeassistant.const import CONF_MODE
from homeassistant.setup import async_setup_component

from . import setup_config_entry
from .const import MOCK_CONFIG_DATA

if TYPE_CHECKING:
    from home_disconnect.testutils import MockAppliance
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.typing import ClientSessionGenerator


async def test_export_view_returns_safe_zip(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """The safe variant returns a ZIP without the key, with the expected filename."""
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, {**MOCK_CONFIG_DATA, CONF_MODE: "AES"})
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    hass.http.register_view(HCExportView())
    client = await hass_client()

    resp = await client.get(f"/api/homeconnect_ws/export/{entry.entry_id}/safe")

    assert resp.status == 200
    assert resp.content_type == "application/zip"
    assert "fake_brand_Fake_vib_profile_safe.zip" in resp.headers["Content-Disposition"]


async def test_export_view_returns_full_zip(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """The full variant returns a ZIP including the key, with the expected filename."""
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, {**MOCK_CONFIG_DATA, CONF_MODE: "AES"})
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    hass.http.register_view(HCExportView())
    client = await hass_client()

    resp = await client.get(f"/api/homeconnect_ws/export/{entry.entry_id}/full")

    assert resp.status == 200
    assert resp.content_type == "application/zip"
    assert "fake_brand_Fake_vib_profile_full.zip" in resp.headers["Content-Disposition"]


async def test_export_view_unknown_entry_returns_404(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """An unknown config entry id returns 404, not a crash."""
    assert await async_setup_component(hass, "http", {})
    hass.http.register_view(HCExportView())
    client = await hass_client()

    resp = await client.get("/api/homeconnect_ws/export/does-not-exist/safe")

    assert resp.status == 404


async def test_export_view_requires_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
    mock_appliance: MockAppliance,
    patch_entity_description: None,
) -> None:
    """
    A non-admin user is refused, safe or full.

    A plain unsigned link is only safe to hand out this way behind admin
    auth - matches HA core's own DownloadDiagnosticsView, which gates
    comparably sensitive data the same way instead of a signed, expiring URL.
    """
    assert await async_setup_component(hass, "http", {})
    assert await setup_config_entry(hass, {**MOCK_CONFIG_DATA, CONF_MODE: "AES"})
    entry = hass.config_entries.async_entries("homeconnect_ws")[0]

    hass.http.register_view(HCExportView())
    client = await hass_client(hass_read_only_access_token)

    for variant in ("safe", "full"):
        resp = await client.get(f"/api/homeconnect_ws/export/{entry.entry_id}/{variant}")
        assert resp.status == 401
