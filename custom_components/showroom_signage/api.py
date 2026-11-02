"""What the Signage page (panel.js) talks to: websocket commands and uploads.

Any logged-in user may use them: the page is for the people who run the
screens, not only admins.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import timedelta
from pathlib import Path
import re

from aiohttp import web
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .schedule import (
    async_set_enabled,
    async_switch_screen,
    default_schedule,
    describe as describe_schedule,
    effective,
    screen_mode,
)
from .const import (
    CONF_DEFAULT_SCHEDULE,
    CONF_POWER_ENTITY,
    CONF_SCHEDULE,
    CONF_WORKDAY_ENTITY,
    CONF_FILES,
    CONF_KIND,
    CONF_NAME,
    CONF_PICTURE_SECONDS,
    CONF_PLAYLIST,
    CONF_PLAYLISTS,
    CONF_SCREENS,
    CONF_SHUFFLE,
    DEFAULT_PICTURE_SECONDS,
    DOMAIN,
    IMAGE_EXTENSIONS,
    KIND_CAST,
    KIND_PC,
    THUMB_URL,
    VIDEO_EXTENSIONS,
)

UPLOAD_URL = "/api/showroom_signage/upload"
MAX_UPLOAD = 1024 * 1024 * 1024  # 1 GB


def _entry(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Showroom signage is not loaded")
    return entries[0]


def _sign_thumb(hass: HomeAssistant, info: dict | None) -> str | None:
    if not info or not info.get("thumb"):
        return None
    return async_sign_path(
        hass,
        THUMB_URL.format(key=f"{info['thumb']}.jpg"),
        timedelta(days=1),
        use_content_user=True,
    )


def _name(hass: HomeAssistant, entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    return state.name if state else entity_id


def _save(hass: HomeAssistant, entry, options: dict) -> None:
    # saving reloads the integration; playing screens carry on
    hass.config_entries.async_update_entry(entry, options=options)


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_state,
        ws_save_playlist,
        ws_delete_playlist,
        ws_set_screen,
        ws_screen_power,
        ws_delete_file,
        ws_set_schedule,
        ws_set_default_schedule,
        ws_set_enabled,
    ):
        websocket_api.async_register_command(hass, command)
    hass.http.register_view(UploadView(hass))


@websocket_api.websocket_command({vol.Required("type"): "showroom_signage/state"})
@websocket_api.async_response
async def ws_state(hass, connection, msg):
    from . import async_get_library
    from .pc import PcScreen

    entry = _entry(hass)
    library = await async_get_library(hass)
    rels = await library.async_files()
    limit = asyncio.Semaphore(4)

    async def describe(rel):
        async with limit:
            info = await library.async_info(rel)
        return {
            "name": rel,
            "title": library.title(rel),
            "kind": library.kind(rel),
            "duration": info and info.get("duration"),
            "thumb": _sign_thumb(hass, info),
        }

    files = await asyncio.gather(*(describe(rel) for rel in rels))
    thumbs = {f["name"]: f["thumb"] for f in files}
    playlists = [
        {
            "name": name,
            "files": pl.get(CONF_FILES, []),
            "picture_seconds": pl.get(CONF_PICTURE_SECONDS, DEFAULT_PICTURE_SECONDS),
            "shuffle": pl.get(CONF_SHUFFLE, True),
        }
        for name, pl in sorted(entry.options.get(CONF_PLAYLISTS, {}).items(), key=lambda x: x[0].lower())
    ]
    screens = []
    for screen_id, player in entry.runtime_data.items():
        screen = player.screen
        item = {
            "id": screen_id,
            "name": screen.get(CONF_NAME) or screen_id,
            "kind": screen.get(CONF_KIND, KIND_CAST),
            "playlist": screen.get(CONF_PLAYLIST),
            "picture_seconds": screen.get(CONF_PICTURE_SECONDS) or 0,
            "enabled": screen.get("enabled", True),
            "mode": screen_mode(screen),
            "schedule": {
                "days": [0, 1, 2, 3, 4], "start": "08:30", "end": "18:00", "keep_on": False,
                **{k: v for k, v in (screen.get(CONF_SCHEDULE) or {}).items() if k in ("days", "start", "end", "keep_on")},
            },
            "schedule_text": describe_schedule(effective(entry.options, screen)),
            "keep_on": bool((effective(entry.options, screen) or {}).get("keep_on")),
            "workday_name": _name(hass, (effective(entry.options, screen) or {}).get("workday_entity")),
            "power_name": _name(hass, screen.get(CONF_POWER_ENTITY)),
        }
        if isinstance(player, PcScreen):
            status = player.status if player.online else {}
            rel = status.get("file")
            item.update(
                online=player.online,
                state=status.get("state", "off") if player.online else "offline",
                now_file=rel,
                now_title=library.title(rel) if rel else None,
            )
        else:
            item.update(
                online=True,
                state="playing" if player.running else "stopped",
                now_file=player.now_file,
                now_title=player.now_showing,
            )
        item["now_thumb"] = thumbs.get(item["now_file"])
        screens.append(item)
    screens.sort(key=lambda s: s["name"].lower())
    default = default_schedule(entry.options)
    connection.send_result(
        msg["id"],
        {
            "files": files,
            "playlists": playlists,
            "screens": screens,
            "default_schedule": {
                **{k: default[k] for k in ("days", "start", "end", "keep_on")},
                "text": describe_schedule(default),
                "workday_name": _name(hass, default.get("workday_entity")),
            },
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "showroom_signage/save_playlist",
        vol.Optional("old_name"): str,
        vol.Required("name"): vol.All(str, vol.Strip, vol.Length(min=1, max=60)),
        vol.Required("files"): [str],
        vol.Required("picture_seconds"): vol.All(vol.Coerce(int), vol.Range(min=1, max=86400)),
        vol.Required("shuffle"): bool,
    }
)
@callback
def ws_save_playlist(hass, connection, msg):
    entry = _entry(hass)
    options = copy.deepcopy(dict(entry.options))
    playlists = options.setdefault(CONF_PLAYLISTS, {})
    old, name = msg.get("old_name"), msg["name"]
    if name != old and name in playlists:
        connection.send_error(msg["id"], "name_exists", "There is already a playlist with that name.")
        return
    if old and old != name:
        playlists.pop(old, None)
        for screen in options.get(CONF_SCREENS, {}).values():
            if screen.get(CONF_PLAYLIST) == old:
                screen[CONF_PLAYLIST] = name
    playlists[name] = {
        CONF_FILES: msg["files"],
        CONF_PICTURE_SECONDS: msg["picture_seconds"],
        CONF_SHUFFLE: msg["shuffle"],
    }
    _save(hass, entry, options)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "showroom_signage/delete_playlist", vol.Required("name"): str}
)
@callback
def ws_delete_playlist(hass, connection, msg):
    entry = _entry(hass)
    options = copy.deepcopy(dict(entry.options))
    users = [
        s.get(CONF_NAME) or sid
        for sid, s in options.get(CONF_SCREENS, {}).items()
        if s.get(CONF_PLAYLIST) == msg["name"]
    ]
    if users:
        connection.send_error(
            msg["id"], "in_use", "Screens still play this playlist: " + ", ".join(users)
        )
        return
    options.get(CONF_PLAYLISTS, {}).pop(msg["name"], None)
    _save(hass, entry, options)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "showroom_signage/set_screen",
        vol.Required("screen_id"): str,
        vol.Optional("playlist"): str,
        vol.Optional("picture_seconds"): vol.All(vol.Coerce(int), vol.Range(min=0, max=86400)),
    }
)
@callback
def ws_set_screen(hass, connection, msg):
    entry = _entry(hass)
    options = copy.deepcopy(dict(entry.options))
    screen = options.get(CONF_SCREENS, {}).get(msg["screen_id"])
    if screen is None:
        connection.send_error(msg["id"], "not_found", "No such screen")
        return
    if "playlist" in msg:
        if msg["playlist"] not in options.get(CONF_PLAYLISTS, {}):
            connection.send_error(msg["id"], "not_found", "No such playlist")
            return
        screen[CONF_PLAYLIST] = msg["playlist"]
    if "picture_seconds" in msg:
        screen[CONF_PICTURE_SECONDS] = msg["picture_seconds"]
    _save(hass, entry, options)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "showroom_signage/screen_power",
        vol.Required("screen_id"): str,
        vol.Required("on"): bool,
    }
)
@callback
def ws_screen_power(hass, connection, msg):
    """Start or stop a Cast TV's playlist by hand (the TV's power is left alone)."""
    from .player import ScreenPlayer

    player = _entry(hass).runtime_data.get(msg["screen_id"])
    if not isinstance(player, ScreenPlayer):
        connection.send_error(msg["id"], "not_supported", "Only Cast TVs can be started here")
        return
    async_switch_screen(hass, player.screen_id, msg["on"], power=False)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "showroom_signage/delete_file", vol.Required("name"): str}
)
@websocket_api.async_response
async def ws_delete_file(hass, connection, msg):
    """Delete a file from the media folder, if no playlist uses it."""
    from . import async_get_library

    entry = _entry(hass)
    name = msg["name"]
    used = [
        pl_name
        for pl_name, pl in entry.options.get(CONF_PLAYLISTS, {}).items()
        if name in pl.get(CONF_FILES, [])
    ]
    if used:
        connection.send_error(msg["id"], "in_use", "Used by playlist " + ", ".join(used))
        return
    library = await async_get_library(hass)
    path = (library.root / name).resolve()
    if library.root.resolve() not in path.parents or name not in await library.async_files():
        connection.send_error(msg["id"], "not_found", "No such file")
        return
    await hass.async_add_executor_job(path.unlink)
    connection.send_result(msg["id"])


class UploadView(HomeAssistantView):
    """Upload pictures and videos into the media folder (top level)."""

    url = UPLOAD_URL
    name = f"api:{DOMAIN}:upload"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        from . import async_get_library

        hass = self.hass
        request._client_max_size = MAX_UPLOAD  # noqa: SLF001
        library = await async_get_library(hass)
        reader = await request.multipart()
        saved = []
        while (field := await reader.next()) is not None:
            if field.name != "file" or not field.filename:
                continue
            name = Path(field.filename).name
            name = re.sub(r"[\x00-\x1f/\\\\]", "", name).strip()
            if not name or name.startswith(".") or Path(name).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                return self.json_message(f"Not a picture or video: {field.filename}", 400)
            target = library.root / name
            if await hass.async_add_executor_job(target.exists):
                return self.json_message(f"There is already a file called {name}", 409)
            part = target.with_name(f".{name}.part")
            handle = await hass.async_add_executor_job(part.open, "wb")
            try:
                while chunk := await field.read_chunk(1 << 20):
                    await hass.async_add_executor_job(handle.write, chunk)
            finally:
                await hass.async_add_executor_job(handle.close)
            await hass.async_add_executor_job(part.replace, target)
            saved.append(name)
        return self.json({"saved": saved})


_TIME = vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$")


_SCHEDULE_FIELDS = {
    vol.Required("days"): [vol.All(int, vol.Range(min=0, max=6))],
    vol.Required("start"): _TIME,
    vol.Required("end"): _TIME,
    vol.Optional("keep_on", default=False): bool,
}


def _schedule_from(msg) -> dict:
    return {
        "days": sorted(set(msg["days"])),
        "start": msg["start"],
        "end": msg["end"],
        "keep_on": msg["keep_on"],
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "showroom_signage/set_schedule",
        vol.Required("screen_id"): str,
        vol.Required("mode"): vol.In(["default", "own", "none"]),
        vol.Optional("days", default=[0, 1, 2, 3, 4]): [vol.All(int, vol.Range(min=0, max=6))],
        vol.Optional("start", default="08:30"): _TIME,
        vol.Optional("end", default="18:00"): _TIME,
        vol.Optional("keep_on", default=False): bool,
    }
)
@callback
def ws_set_schedule(hass, connection, msg):
    """A screen's schedule: the default one, its own, or none."""
    entry = _entry(hass)
    options = copy.deepcopy(dict(entry.options))
    screen = options.get(CONF_SCREENS, {}).get(msg["screen_id"])
    if screen is None:
        connection.send_error(msg["id"], "not_found", "No such screen")
        return
    if msg["mode"] == "own" and msg["start"] == msg["end"]:
        connection.send_error(msg["id"], "invalid", "Start and end can't be the same")
        return
    screen[CONF_SCHEDULE] = {"mode": msg["mode"], **_schedule_from(msg)}
    _save(hass, entry, options)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "showroom_signage/set_default_schedule", **_SCHEDULE_FIELDS}
)
@callback
def ws_set_default_schedule(hass, connection, msg):
    """The default schedule (its workday entity is set in Configure)."""
    entry = _entry(hass)
    if msg["start"] == msg["end"]:
        connection.send_error(msg["id"], "invalid", "Start and end can't be the same")
        return
    options = copy.deepcopy(dict(entry.options))
    options[CONF_DEFAULT_SCHEDULE] = {
        **(options.get(CONF_DEFAULT_SCHEDULE) or {}),
        **_schedule_from(msg),
    }
    _save(hass, entry, options)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "showroom_signage/set_enabled",
        vol.Required("screen_id"): str,
        vol.Required("enabled"): bool,
    }
)
@callback
def ws_set_enabled(hass, connection, msg):
    entry = _entry(hass)
    if msg["screen_id"] not in entry.options.get(CONF_SCREENS, {}):
        connection.send_error(msg["id"], "not_found", "No such screen")
        return
    async_set_enabled(hass, entry, msg["screen_id"], msg["enabled"])
    connection.send_result(msg["id"])
