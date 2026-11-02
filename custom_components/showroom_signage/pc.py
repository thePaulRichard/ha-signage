"""A PC screen: a PC that plays the playlist itself (the signage agent).

Home Assistant publishes the playlist to MQTT, retained, at
showroom_signage/<screen>/playlist: the file names, a version of each file
(size and time) and a signed download link. The agent downloads what it is
missing and plays the list. It reports what is on screen at .../status and
online/offline at .../availability, and takes play, pause, next and previous
at .../command. The links expire, so the playlist is published again every
PC_REPUBLISH_HOURS.
"""

from __future__ import annotations

from datetime import timedelta
import json
import logging
import time
from urllib.parse import quote

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_FILES,
    CONF_PICTURE_SECONDS,
    CONF_PLAYLIST,
    CONF_SHUFFLE,
    DEFAULT_PICTURE_SECONDS,
    MQTT_PREFIX,
    PC_REPUBLISH_HOURS,
    PC_URL_DAYS,
    THUMB_URL,
    signal_screen_update,
)
from .media import MediaLibrary

_LOGGER = logging.getLogger(__name__)


class PcScreen:
    """Keeps a PC's playlist up to date and follows what it shows."""

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
        self.topic = f"{MQTT_PREFIX}/{screen_id}"
        self.online = False
        self.status: dict = {}
        self.status_received: float | None = None
        self._unsubs: list = []
        self._thumbs: dict[str, tuple[str, float]] = {}  # file: (signed url, when)

    async def async_start(self) -> None:
        from homeassistant.components import mqtt

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            _LOGGER.error("MQTT is not set up: PC screen %s can't work", self.screen_id)
            return
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass, f"{self.topic}/status", self._status_message
            )
        )
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass, f"{self.topic}/availability", self._availability_message
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._async_republish,
                timedelta(hours=PC_REPUBLISH_HOURS),
            )
        )
        await self.async_publish_playlist()

    def stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    async def _async_republish(self, _now) -> None:
        await self.async_publish_playlist()

    def picture_seconds(self) -> int:
        return int(
            self.screen.get(CONF_PICTURE_SECONDS)
            or (self.playlist or {}).get(CONF_PICTURE_SECONDS)
            or DEFAULT_PICTURE_SECONDS
        )

    async def async_publish_playlist(self) -> None:
        from homeassistant.components import mqtt

        files = []
        for rel in (self.playlist or {}).get(CONF_FILES, []):
            info = await self.library.async_info(rel)  # also makes the thumbnail
            if info is None:
                continue
            path = f"/media/local/{rel}"
            signed = async_sign_path(
                self.hass, path, timedelta(days=PC_URL_DAYS), use_content_user=True
            )
            query = signed.split("?", 1)[1]
            files.append({"name": rel, "version": info["sig"], "url": f"{quote(path)}?{query}"})
        payload = {
            "playlist": self.screen.get(CONF_PLAYLIST),
            "picture_seconds": self.picture_seconds(),
            "shuffle": (self.playlist or {}).get(CONF_SHUFFLE, True),
            "files": files,
            "published": int(time.time()),
        }
        await mqtt.async_publish(
            self.hass, f"{self.topic}/playlist", json.dumps(payload), qos=1, retain=True
        )

    async def async_command(self, command: str) -> None:
        from homeassistant.components import mqtt

        await mqtt.async_publish(self.hass, f"{self.topic}/command", command, qos=1)

    @callback
    def _status_message(self, msg) -> None:
        try:
            self.status = json.loads(msg.payload)
        except ValueError:
            _LOGGER.warning("Bad status from %s: %s", self.screen_id, msg.payload)
            return
        self.status_received = time.time()
        async_dispatcher_send(self.hass, signal_screen_update(self.screen_id))
        if (rel := self.status.get("file")) and rel not in self._thumbs:
            self.hass.async_create_task(self._async_thumb(rel))

    @callback
    def _availability_message(self, msg) -> None:
        self.online = msg.payload == "online"
        async_dispatcher_send(self.hass, signal_screen_update(self.screen_id))

    async def _async_thumb(self, rel: str) -> None:
        info = await self.library.async_info(rel)
        if info and info.get("thumb"):
            url = async_sign_path(
                self.hass,
                THUMB_URL.format(key=f"{info['thumb']}.jpg"),
                timedelta(days=2),
                use_content_user=True,
            )
            self._thumbs[rel] = (url, time.time())
            async_dispatcher_send(self.hass, signal_screen_update(self.screen_id))

    def thumb(self, rel: str | None) -> str | None:
        """Signed thumbnail URL of a file (signed again after a day)."""
        if not rel or rel not in self._thumbs:
            return None
        url, signed_at = self._thumbs[rel]
        if time.time() - signed_at > 86400:
            del self._thumbs[rel]
            self.hass.async_create_task(self._async_thumb(rel))
        return url
