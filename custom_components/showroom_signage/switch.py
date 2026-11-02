"""A switch per screen: Enabled.

On: the screen follows its schedule (starting now if it is in its hours; with
no schedule it starts now). Turning it on while on starts the playlist again
with a new shuffle. Off: the screen is stopped and its TV powered off, and the
schedule leaves it alone until it is enabled again.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import CONF_ENABLED, CONF_MEDIA_PLAYER, CONF_PLAYLIST
from .entity import ScreenEntity
from .player import ScreenPlayer
from .schedule import async_set_enabled, async_switch_screen


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ScreenSwitch(entry, player) for player in entry.runtime_data.values())


class ScreenSwitch(ScreenEntity, SwitchEntity):
    _attr_name = "Signage"
    _attr_icon = "mdi:television-play"

    def __init__(self, entry, player) -> None:
        super().__init__(entry, player, "signage")

    @property
    def is_on(self) -> bool:
        return self.player.screen.get(CONF_ENABLED, True)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "playlist": self.player.screen.get(CONF_PLAYLIST),
            "media_player": self.player.screen.get(CONF_MEDIA_PLAYER),
        }
        if isinstance(self.player, ScreenPlayer):
            attrs["playing"] = self.player.running
            attrs["now_showing"] = self.player.now_showing
        return attrs

    async def async_turn_on(self, **kwargs) -> None:
        if self.is_on:  # already enabled: start again (new shuffle), like before
            async_switch_screen(self.hass, self.player.screen_id, True, power=False)
        else:
            async_set_enabled(self.hass, self.entry, self.player.screen_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        async_set_enabled(self.hass, self.entry, self.player.screen_id, False)
