"""Base entity: one device per screen."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONF_NAME, DOMAIN, signal_screen_update
from .player import ScreenPlayer


class ScreenEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, player: ScreenPlayer, key: str) -> None:
        self.entry = entry
        self.player = player
        self._attr_unique_id = f"{player.screen_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player.screen_id)},
            name=player.screen.get(CONF_NAME) or player.screen_id,
            manufacturer="Signage",
            model="Screen",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_screen_update(self.player.screen_id), self._update
            )
        )

    @callback
    def _update(self) -> None:
        self.async_write_ha_state()
