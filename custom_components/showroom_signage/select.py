"""A select per screen: which playlist it plays."""

from __future__ import annotations

import copy

from homeassistant.components.select import SelectEntity

from .const import CONF_PLAYLIST, CONF_PLAYLISTS, CONF_SCREENS
from .entity import ScreenEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        PlaylistSelect(entry, player) for player in entry.runtime_data.values()
    )


class PlaylistSelect(ScreenEntity, SelectEntity):
    _attr_name = "Playlist"
    _attr_icon = "mdi:playlist-play"

    def __init__(self, entry, player) -> None:
        super().__init__(entry, player, "playlist")
        self._attr_options = sorted(entry.options.get(CONF_PLAYLISTS, {}), key=str.lower)

    @property
    def current_option(self) -> str | None:
        return self.player.screen.get(CONF_PLAYLIST)

    async def async_select_option(self, option: str) -> None:
        options = copy.deepcopy(dict(self.entry.options))
        options[CONF_SCREENS][self.player.screen_id][CONF_PLAYLIST] = option
        # saving reloads the integration; a playing screen carries on with it
        self.hass.config_entries.async_update_entry(self.entry, options=options)
