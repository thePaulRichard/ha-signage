"""Plays a playlist on one screen (a Cast TV), in a loop."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import math
import random
import time

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_FILES,
    CONF_MEDIA_PLAYER,
    CONF_PICTURE_SECONDS,
    CONF_PLAYLIST,
    CONF_SHUFFLE,
    DEFAULT_PICTURE_SECONDS,
    DOMAIN,
    THUMB_URL,
    signal_screen_update,
)
from .media import MediaLibrary

_LOGGER = logging.getLogger(__name__)
RETRY_SECONDS = 30
EMPTY_WAIT_SECONDS = 60
VIDEO_FALLBACK_SECONDS = 60


class ScreenPlayer:
    """The slideshow loop for one screen."""

    def __init__(
        self,
        hass: HomeAssistant,
        library: MediaLibrary,
        screen_id: str,
        screen: dict,
        playlist: dict | None,
    ) -> None:
        self.hass = hass
        self.library = library
        self.screen_id = screen_id
        self.screen = screen
        self.playlist = playlist
        self.now_showing: str | None = None
        self.now_file: str | None = None
        self.now_kind: str | None = None
        self.now_thumb_url: str | None = None
        self.now_started: float | None = None  # time.time() when the file was cast
        self.now_seconds: float | None = None  # how long it stays
        self.paused = False
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()  # pause, play, next or previous
        self._jump = 0  # +1 next, -1 previous

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start, or start again with a new shuffle."""
        self.stop()
        self._task = self.hass.async_create_background_task(
            self._run(), f"{DOMAIN} {self.screen_id}"
        )
        self._changed()

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self.now_showing = self.now_file = self.now_kind = self.now_thumb_url = None
        self.now_started = self.now_seconds = None
        self.paused = False
        self._jump = 0
        self._changed()

    # controls (from the media player entity)
    async def async_pause(self) -> None:
        if not self.running or self.paused:
            return
        self.paused = True
        self._wake.set()
        if self.now_kind == "video":
            await self._cast_command("media_pause")
        self._changed()

    async def async_play(self) -> None:
        if not self.running:
            self.start()
            return
        if self.paused:
            self.paused = False
            self._wake.set()
            if self.now_kind == "video":
                await self._cast_command("media_play")
            self._changed()

    def skip(self, step: int) -> None:
        if self.running:
            self.paused = False
            self._jump = step
            self._wake.set()

    async def _cast_command(self, service: str) -> None:
        try:
            await self.hass.services.async_call(
                "media_player", service, {"entity_id": self.screen[CONF_MEDIA_PLAYER]}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("%s: %s failed: %s", self.screen[CONF_MEDIA_PLAYER], service, err)

    def _changed(self) -> None:
        async_dispatcher_send(self.hass, signal_screen_update(self.screen_id))

    def _picture_seconds(self) -> int:
        return int(
            self.screen.get(CONF_PICTURE_SECONDS)
            or (self.playlist or {}).get(CONF_PICTURE_SECONDS)
            or DEFAULT_PICTURE_SECONDS
        )

    async def _run(self) -> None:
        while True:
            files = list((self.playlist or {}).get(CONF_FILES, []))
            if self.playlist is None or self.playlist.get(CONF_SHUFFLE, True):
                random.shuffle(files)
            played = False
            i = 0
            while i < len(files):
                rel = files[i]
                info = await self.library.async_info(rel)
                if info is None:
                    i += 1
                    continue  # the file was removed from the media folder
                if not await self._play(rel, info):
                    await asyncio.sleep(RETRY_SECONDS)
                    i += 1
                    continue
                played = True
                seconds = await self._wait_seconds(info)
                self.now_seconds = seconds
                self._changed()
                i = max(0, i + await self._wait(seconds))
            if not played:
                self.now_showing = None
                self._changed()
                await asyncio.sleep(EMPTY_WAIT_SECONDS)

    async def _wait(self, seconds: float) -> int:
        """Wait while the file shows; paused waits stop the clock. Returns the step."""
        loop = asyncio.get_running_loop()
        remaining = seconds
        while True:
            self._wake.clear()
            if self._jump:
                step, self._jump = self._jump, 0
                return step
            if remaining <= 0:
                return 1
            started, was_paused = loop.time(), self.paused
            try:
                async with asyncio.timeout(None if was_paused else remaining):
                    await self._wake.wait()
            except TimeoutError:
                return 1
            if not was_paused:  # paused: the clock stands still
                remaining -= loop.time() - started

    async def _play(self, rel: str, info: dict) -> bool:
        title = self.library.title(rel)
        metadata: dict = {"metadataType": 0, "title": title}
        thumb_url = None
        if info.get("thumb"):
            thumb_url = async_sign_path(
                self.hass,
                THUMB_URL.format(key=f"{info['thumb']}.jpg"),
                timedelta(days=2),
                use_content_user=True,
            )
            metadata["images"] = [{"url": thumb_url}]
        try:
            async with asyncio.timeout(30):
                await self.hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": self.screen[CONF_MEDIA_PLAYER],
                        "media_content_id": f"media-source://media_source/local/{rel}",
                        "media_content_type": info["kind"],
                        "extra": {"metadata": metadata},
                    },
                    blocking=True,
                )
        except Exception as err:  # noqa: BLE001 - a TV being off must not stop the loop
            _LOGGER.warning(
                "%s: could not play %s: %s", self.screen[CONF_MEDIA_PLAYER], rel, err
            )
            return False
        self.now_showing = title
        self.now_file = rel
        self.now_kind = info["kind"]
        self.now_thumb_url = thumb_url
        self.now_started = time.time()
        self.now_seconds = None
        self._changed()
        return True

    async def _wait_seconds(self, info: dict) -> float:
        if info["kind"] == "image":
            return self._picture_seconds()
        if info.get("duration"):
            return math.ceil(info["duration"]) + 1
        # no ffmpeg: ask the TV how long the video is
        for _ in range(15):
            await asyncio.sleep(1)
            state = self.hass.states.get(self.screen[CONF_MEDIA_PLAYER])
            if state and (duration := state.attributes.get("media_duration")):
                return max(1, math.ceil(duration) - 1)
        return VIDEO_FALLBACK_SECONDS
