"""A media player per screen: what it shows (playlist, title, picture), with
play/pause/next/previous. PC screens report over MQTT; for a Cast TV it is the
slideshow loop Home Assistant runs, checked against the Chromecast's state."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .entity import ScreenEntity
from .media import MediaLibrary
from .pc import PcScreen
from .player import ScreenPlayer

STATES = {"playing": MediaPlayerState.PLAYING, "paused": MediaPlayerState.PAUSED}
CAST_APP = "Default Media Receiver"
CONTROLS = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        PcMediaPlayer(entry, player) if isinstance(player, PcScreen) else CastSignagePlayer(entry, player)
        for player in entry.runtime_data.values()
        if isinstance(player, (PcScreen, ScreenPlayer))
    )


class PcMediaPlayer(ScreenEntity, MediaPlayerEntity):
    _attr_name = "Signage"
    _attr_media_image_remotely_accessible = True  # signed URLs
    _attr_supported_features = CONTROLS

    def __init__(self, entry, player: PcScreen) -> None:
        super().__init__(entry, player, "media_player")

    @property
    def available(self) -> bool:
        return self.player.online

    @property
    def _status(self) -> dict:
        return self.player.status if self.player.online else {}

    @property
    def state(self):
        return STATES.get(self._status.get("state"), MediaPlayerState.OFF)

    @property
    def app_name(self) -> str | None:
        return self.player.screen.get("playlist")

    @property
    def media_title(self) -> str | None:
        rel = self._status.get("file")
        return MediaLibrary.title(rel) if rel and self.state != MediaPlayerState.OFF else None

    @property
    def media_image_url(self) -> str | None:
        if self.state == MediaPlayerState.OFF:
            return None
        return self.player.thumb(self._status.get("file"))

    @property
    def media_duration(self) -> float | None:
        return self._status.get("duration") if self.state != MediaPlayerState.OFF else None

    @property
    def media_position(self) -> float | None:
        return self._status.get("position") if self.state != MediaPlayerState.OFF else None

    @property
    def media_position_updated_at(self):
        received = self.player.status_received
        return dt_util.utc_from_timestamp(received) if received else None

    async def async_media_play(self) -> None:
        await self.player.async_command("play")

    async def async_media_pause(self) -> None:
        await self.player.async_command("pause")

    async def async_media_next_track(self) -> None:
        await self.player.async_command("next")

    async def async_media_previous_track(self) -> None:
        await self.player.async_command("previous")


class CastSignagePlayer(ScreenEntity, MediaPlayerEntity):
    """The slideshow on a Cast TV. Idle (not playing) when the Chromecast has left it,
    so a universal media player with this as its first child falls back to the TV."""

    _attr_name = "Signage"
    _attr_media_image_remotely_accessible = True  # signed URLs
    _attr_supported_features = CONTROLS

    def __init__(self, entry, player: ScreenPlayer) -> None:
        super().__init__(entry, player, "media_player")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if cast := self.player.screen.get("media_player"):
            self.async_on_remove(
                async_track_state_change_event(self.hass, [cast], self._cast_changed)
            )

    @callback
    def _cast_changed(self, _event) -> None:
        self.async_write_ha_state()

    @property
    def _cast(self):
        return self.hass.states.get(self.player.screen.get("media_player", ""))

    @property
    def state(self):
        if not self.player.running:
            return MediaPlayerState.OFF
        cast = self._cast
        if (
            cast is None
            or cast.state in ("off", "idle", "standby", "unavailable", "unknown")
            or cast.attributes.get("app_name") not in (None, CAST_APP)
            or not self.player.now_file
        ):
            return MediaPlayerState.IDLE  # on, but the TV isn't showing it
        return MediaPlayerState.PAUSED if self.player.paused else MediaPlayerState.PLAYING

    @property
    def _showing(self) -> bool:
        return self.state in (MediaPlayerState.PLAYING, MediaPlayerState.PAUSED)

    @property
    def app_name(self) -> str | None:
        return self.player.screen.get("playlist")

    @property
    def media_content_type(self) -> str | None:
        return self.player.now_kind if self._showing else None

    @property
    def media_title(self) -> str | None:
        return self.player.now_showing if self._showing else None

    @property
    def media_image_url(self) -> str | None:
        return self.player.now_thumb_url if self._showing else None

    @property
    def media_duration(self) -> float | None:
        if not self._showing or self.player.now_kind != "video":
            return None
        return self._cast.attributes.get("media_duration")

    @property
    def media_position(self) -> float | None:
        if not self._showing or self.player.now_kind != "video":
            return None
        return self._cast.attributes.get("media_position")

    @property
    def media_position_updated_at(self):
        if not self._showing or self.player.now_kind != "video":
            return None
        return self._cast.attributes.get("media_position_updated_at")

    async def async_media_play(self) -> None:
        await self.player.async_play()

    async def async_media_pause(self) -> None:
        await self.player.async_pause()

    async def async_media_next_track(self) -> None:
        self.player.skip(1)

    async def async_media_previous_track(self) -> None:
        self.player.skip(-1)
