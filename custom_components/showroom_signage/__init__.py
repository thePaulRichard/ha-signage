"""Showroom signage: playlists of pictures and videos for the office TVs.

Files come from Home Assistant's local media folder (Media > My media).
Playlists and screens are set up in the integration's Configure dialog;
each screen gets a switch (play the playlist in a loop) and a playlist select.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_KIND,
    CONF_PLAYLIST,
    CONF_PLAYLISTS,
    CONF_SCREENS,
    DOMAIN,
    KIND_PC,
    PLATFORMS,
)
from .media import MediaLibrary, ThumbnailView
from .pc import PcScreen
from .player import ScreenPlayer

DATA_LIBRARY = f"{DOMAIN}_library"
DATA_PANEL = f"{DOMAIN}_panel"
PANEL_URL = "signage"
STATIC_URL = "/showroom_signage_static"
# Screens that were playing; kept across reloads (after a settings change)
# so the screens carry on. Empty after a Home Assistant restart.
DATA_RUNNING = f"{DOMAIN}_running"


async def async_get_library(hass: HomeAssistant) -> MediaLibrary:
    """The shared media library (set up once)."""
    if DATA_LIBRARY not in hass.data:
        library = MediaLibrary(hass)
        await library.async_load()
        hass.http.register_view(ThumbnailView(hass, library.thumb_dir))
        hass.data[DATA_LIBRARY] = library
    return hass.data[DATA_LIBRARY]


async def _async_setup_panel(hass: HomeAssistant) -> None:
    """The Signage page in the sidebar, for everyone (not only admins)."""
    from pathlib import Path

    from homeassistant.components import panel_custom
    from homeassistant.components.http import StaticPathConfig

    from . import api

    if DATA_PANEL not in hass.data:  # once per Home Assistant run
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "www"), False)]
        )
        api.async_register(hass)
        hass.data[DATA_PANEL] = True
    panel_js = Path(__file__).parent / "www" / "panel.js"
    version = (await hass.async_add_executor_job(panel_js.stat)).st_mtime_ns
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="showroom-signage-panel",
        sidebar_title="Signage",
        sidebar_icon="mdi:television-play",
        module_url=f"{STATIC_URL}/panel.js?v={version}",
        require_admin=False,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    library = await async_get_library(hass)
    running: set[str] = hass.data.setdefault(DATA_RUNNING, set())
    playlists = entry.options.get(CONF_PLAYLISTS, {})
    players = {}
    for screen_id, screen in entry.options.get(CONF_SCREENS, {}).items():
        cls = PcScreen if screen.get(CONF_KIND) == KIND_PC else ScreenPlayer
        players[screen_id] = cls(
            hass, library, screen_id, screen, playlists.get(screen.get(CONF_PLAYLIST))
        )
    entry.runtime_data = players
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for screen_id, player in players.items():
        if isinstance(player, PcScreen):
            entry.async_create_background_task(
                hass, player.async_start(), f"{DOMAIN} {screen_id}"
            )
        elif screen_id in running:
            player.start()
    from .schedule import Scheduler

    scheduler = Scheduler(hass, entry)
    await scheduler.async_start()
    entry.async_on_unload(scheduler.stop)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    from homeassistant.components import frontend

    if not frontend.async_panel_exists(hass, PANEL_URL):
        await _async_setup_panel(hass)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration deleted: take the page out of the sidebar."""
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    for player in entry.runtime_data.values():
        if isinstance(player, PcScreen):
            player.stop()
        elif player._task is not None:  # stop without forgetting it was running
            player._task.cancel()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
