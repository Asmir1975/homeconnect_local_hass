"""HTTP view for downloading an appliance's exported profile ZIP."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.components.http.decorators import require_admin
from homeassistant.helpers.http import HomeAssistantView

from .const import DOMAIN
from .export_profile import build_profile_zip, filename_stub

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class HCExportView(HomeAssistantView):
    """
    Serve a ZIP export of an appliance's profile, Safe or Full.

    Gated by @require_admin rather than a signed link (matching HA core's
    own DownloadDiagnosticsView, which serves comparably sensitive data the
    same way): a link only an already-logged-in admin can use isn't
    "possession equals access" the way an unauthenticated signed link is,
    so there's no need for either the 5-minute expiry the old signed-link
    approach needed, or Full's old filesystem-write-instead-of-HTTP
    workaround - both variants can just be plain authenticated downloads.
    """

    requires_auth = True
    url = f"/api/{DOMAIN}/export/{{entry_id}}/safe"
    # HomeAssistantView.extra_urls is itself declared as a plain (unannotated)
    # `list[str] = []`, not ClassVar - matching that instead of annotating our
    # own override as ClassVar avoids a "can't override instance variable with
    # class variable" mypy error, same pattern HA core's own DownloadDiagnosticsView uses.
    extra_urls = [f"/api/{DOMAIN}/export/{{entry_id}}/full"]  # noqa: RUF012
    name = f"api:{DOMAIN}:export"

    @require_admin
    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Return the ZIP export for the given config entry."""
        hass: HomeAssistant = request.app["hass"]
        config_entry = hass.config_entries.async_get_entry(entry_id)
        if config_entry is None or config_entry.domain != DOMAIN:
            return web.Response(status=404, text="Unknown config entry")

        full = request.path.endswith("/full")
        try:
            zip_bytes = await hass.async_add_executor_job(
                build_profile_zip,
                config_entry,
                full,
            )
        except (KeyError, TypeError) as err:
            _LOGGER.exception("Failed to build profile export for %s", entry_id)
            return web.Response(status=500, text=f"Could not build export: {err}")

        stub = filename_stub(config_entry)
        variant = "full" if full else "safe"
        return web.Response(
            body=zip_bytes,
            content_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{stub}_profile_{variant}.zip"'},
        )
