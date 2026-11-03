"""Set up Signage, and its Configure dialog: playlists and screens."""

from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    TimeSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

import re

from .const import (
    CONF_DEFAULT_SCHEDULE,
    CONF_ENABLED,
    CONF_POWER_ENTITY,
    CONF_SCHEDULE,
    CONF_START_VOLUME,
    CONF_WORKDAY_ENTITY,
    DAYS,
    CONF_FILES,
    CONF_KIND,
    KIND_CAST,
    KIND_PC,
    CONF_MEDIA_PLAYER,
    CONF_NAME,
    CONF_PICTURE_SECONDS,
    CONF_PLAYLIST,
    CONF_PLAYLISTS,
    CONF_SCREENS,
    CONF_SHUFFLE,
    DEFAULT_PICTURE_SECONDS,
    DOMAIN,
)

CONF_DELETE = "delete"
CONF_SCREEN_ID = "screen_id"
CONF_SCHEDULE_ENABLED = "schedule_enabled"
CONF_DAYS = "days"
CONF_START = "start"
CONF_END = "end"
CONF_KEEP_ON = "keep_on"


CONF_SCHEDULE_MODE = "schedule_mode"
MODES = ["default", "own", "none"]


def _days_selector():
    return SelectSelector(
        SelectSelectorConfig(options=DAYS, multiple=True, mode=SelectSelectorMode.LIST, translation_key="days")
    )


WORKDAY_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain=["binary_sensor", "input_boolean", "schedule", "calendar"])
)


def _schedule_schema() -> dict:
    return {
        vol.Optional(CONF_ENABLED, default=True): BooleanSelector(),
        vol.Required(CONF_SCHEDULE_MODE, default="default"): SelectSelector(
            SelectSelectorConfig(options=MODES, mode=SelectSelectorMode.LIST, translation_key="schedule_mode")
        ),
        vol.Optional(CONF_DAYS, default=DAYS[:5]): _days_selector(),
        vol.Optional(CONF_START, default="08:30:00"): TimeSelector(),
        vol.Optional(CONF_END, default="18:00:00"): TimeSelector(),
        vol.Optional(CONF_KEEP_ON, default=False): BooleanSelector(),
        vol.Optional(CONF_WORKDAY_ENTITY): WORKDAY_SELECTOR,
        vol.Optional(CONF_POWER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=["media_player", "switch", "remote", "input_boolean"])
        ),
        vol.Optional(CONF_START_VOLUME): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER)
        ),
    }


def _times(user_input: dict) -> dict:
    return {
        "days": sorted(DAYS.index(d) for d in user_input.get(CONF_DAYS, [])),
        "start": str(user_input.get(CONF_START, "08:30:00"))[:5],
        "end": str(user_input.get(CONF_END, "18:00:00"))[:5],
        "keep_on": bool(user_input.get(CONF_KEEP_ON)),
    }


def _schedule_from_input(user_input: dict) -> dict:
    return {
        CONF_ENABLED: bool(user_input.get(CONF_ENABLED, True)),
        CONF_SCHEDULE: {"mode": user_input.get(CONF_SCHEDULE_MODE, "default"), **_times(user_input)},
        CONF_WORKDAY_ENTITY: user_input.get(CONF_WORKDAY_ENTITY) or None,
        CONF_POWER_ENTITY: user_input.get(CONF_POWER_ENTITY) or None,
        CONF_START_VOLUME: (
            int(user_input[CONF_START_VOLUME])
            if user_input.get(CONF_START_VOLUME) is not None
            else None
        ),
    }


def _times_suggested(schedule: dict) -> dict:
    return {
        CONF_DAYS: [DAYS[d] for d in schedule.get("days", range(5))],
        CONF_START: f"{schedule.get('start', '08:30')}:00",
        CONF_END: f"{schedule.get('end', '18:00')}:00",
        CONF_KEEP_ON: bool(schedule.get("keep_on")),
    }


def _schedule_suggested(screen: dict) -> dict:
    from .schedule import screen_mode

    values = {
        CONF_ENABLED: screen.get(CONF_ENABLED, True),
        CONF_SCHEDULE_MODE: screen_mode(screen) if screen else "default",
        **_times_suggested(screen.get(CONF_SCHEDULE) or {}),
    }
    for key in (CONF_WORKDAY_ENTITY, CONF_POWER_ENTITY, CONF_START_VOLUME):
        if screen.get(key) is not None:
            values[key] = screen[key]
    return values


class SignageConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            return self.async_show_form(step_id="user")
        from . import async_migrate_from_showroom_signage

        options = await async_migrate_from_showroom_signage(self.hass)
        return self.async_create_entry(
            title="Signage",
            data={},
            options=options or {CONF_PLAYLISTS: {}, CONF_SCREENS: {}},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SignageOptionsFlow()


class SignageOptionsFlow(OptionsFlow):
    def __init__(self) -> None:
        self._playlist: str | None = None
        self._screen: str | None = None

    def _options(self) -> dict:
        options = copy.deepcopy(dict(self.config_entry.options))
        options.setdefault(CONF_PLAYLISTS, {})
        options.setdefault(CONF_SCREENS, {})
        return options

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_playlist",
                "edit_playlist",
                "add_screen",
                "add_pc_screen",
                "edit_screen",
                "default_schedule",
            ],
        )

    # ---- playlists ----

    async def async_step_add_playlist(self, user_input=None):
        return await self._playlist_form("add_playlist", None, user_input)

    async def async_step_edit_playlist(self, user_input=None):
        playlists = self._options()[CONF_PLAYLISTS]
        if not playlists:
            return self.async_abort(reason="no_playlists")
        if user_input is not None:
            self._playlist = user_input[CONF_PLAYLIST]
            return await self.async_step_playlist()
        return self.async_show_form(
            step_id="edit_playlist",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PLAYLIST): SelectSelector(
                        SelectSelectorConfig(
                            options=sorted(playlists, key=str.lower),
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_playlist(self, user_input=None):
        return await self._playlist_form("playlist", self._playlist, user_input)

    async def _playlist_form(self, step_id: str, current: str | None, user_input):
        from . import async_get_library

        options = self._options()
        playlists = options[CONF_PLAYLISTS]
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            in_use = [
                s.get(CONF_NAME) or sid
                for sid, s in options[CONF_SCREENS].items()
                if s.get(CONF_PLAYLIST) == current
            ]
            if current and user_input.get(CONF_DELETE):
                if in_use:
                    errors["base"] = "playlist_in_use"
                else:
                    playlists.pop(current, None)
                    return self.async_create_entry(data=options)
            elif not name:
                errors[CONF_NAME] = "name_required"
            elif name != current and name in playlists:
                errors[CONF_NAME] = "name_exists"
            else:
                if current and name != current:
                    playlists.pop(current, None)
                    for screen in options[CONF_SCREENS].values():
                        if screen.get(CONF_PLAYLIST) == current:
                            screen[CONF_PLAYLIST] = name
                playlists[name] = {
                    CONF_FILES: list(user_input.get(CONF_FILES, [])),
                    CONF_PICTURE_SECONDS: int(user_input[CONF_PICTURE_SECONDS]),
                    CONF_SHUFFLE: bool(user_input[CONF_SHUFFLE]),
                }
                return self.async_create_entry(data=options)

        library = await async_get_library(self.hass)
        existing = playlists.get(current, {}) if current else {}
        files = sorted(
            set(await library.async_files()) | set(existing.get(CONF_FILES, [])),
            key=str.lower,
        )
        schema = {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Optional(CONF_FILES, default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=files, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
            vol.Required(
                CONF_PICTURE_SECONDS, default=DEFAULT_PICTURE_SECONDS
            ): SECONDS,
            vol.Required(CONF_SHUFFLE, default=True): BooleanSelector(),
        }
        if current:
            schema[vol.Optional(CONF_DELETE, default=False)] = BooleanSelector()
        suggested = user_input or (
            {
                CONF_NAME: current,
                CONF_FILES: existing.get(CONF_FILES, []),
                CONF_PICTURE_SECONDS: existing.get(
                    CONF_PICTURE_SECONDS, DEFAULT_PICTURE_SECONDS
                ),
                CONF_SHUFFLE: existing.get(CONF_SHUFFLE, True),
            }
            if current
            else {}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), suggested
            ),
            errors=errors,
            description_placeholders={"playlist": current or ""},
        )

    # ---- screens ----

    async def async_step_add_screen(self, user_input=None):
        return await self._screen_form("add_screen", None, user_input)

    async def async_step_edit_screen(self, user_input=None):
        screens = self._options()[CONF_SCREENS]
        if not screens:
            return self.async_abort(reason="no_screens")
        if user_input is not None:
            self._screen = user_input["screen"]
            if screens[self._screen].get(CONF_KIND) == KIND_PC:
                return await self.async_step_pc_screen()
            return await self.async_step_screen()
        return self.async_show_form(
            step_id="edit_screen",
            data_schema=vol.Schema(
                {
                    vol.Required("screen"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": sid, "label": s.get(CONF_NAME) or sid}
                                for sid, s in sorted(screens.items())
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_screen(self, user_input=None):
        return await self._screen_form("screen", self._screen, user_input)

    async def _screen_form(self, step_id: str, current: str | None, user_input):
        options = self._options()
        playlists = options[CONF_PLAYLISTS]
        screens = options[CONF_SCREENS]
        if not playlists:
            return self.async_abort(reason="no_playlists")
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_MEDIA_PLAYER]
            screen_id = entity_id.split(".", 1)[1]
            if current and user_input.get(CONF_DELETE):
                screens.pop(current, None)
                return self.async_create_entry(data=options)
            if screen_id != current and screen_id in screens:
                errors[CONF_MEDIA_PLAYER] = "screen_exists"
            else:
                if current and screen_id != current:
                    screens.pop(current, None)
                state = self.hass.states.get(entity_id)
                name = (user_input.get(CONF_NAME) or "").strip() or (
                    state.name if state else screen_id
                )
                screens[screen_id] = {
                    CONF_KIND: KIND_CAST,
                    CONF_NAME: name,
                    CONF_MEDIA_PLAYER: entity_id,
                    CONF_PLAYLIST: user_input[CONF_PLAYLIST],
                    CONF_PICTURE_SECONDS: int(user_input.get(CONF_PICTURE_SECONDS) or 0),
                    **_schedule_from_input(user_input),
                }
                return self.async_create_entry(data=options)

        existing = screens.get(current, {}) if current else {}
        schema = {
            vol.Optional(CONF_NAME): TextSelector(),
            vol.Required(CONF_MEDIA_PLAYER): EntitySelector(
                EntitySelectorConfig(domain="media_player")
            ),
            vol.Required(CONF_PLAYLIST): SelectSelector(
                SelectSelectorConfig(
                    options=sorted(playlists, key=str.lower),
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_PICTURE_SECONDS, default=0): SECONDS_OR_ZERO,
            **_schedule_schema(),
        }
        if current:
            schema[vol.Optional(CONF_DELETE, default=False)] = BooleanSelector()
        suggested = user_input or (
            {
                **_schedule_suggested(existing),
                CONF_NAME: existing.get(CONF_NAME),
                CONF_MEDIA_PLAYER: existing.get(CONF_MEDIA_PLAYER),
                CONF_PLAYLIST: existing.get(CONF_PLAYLIST),
                CONF_PICTURE_SECONDS: existing.get(CONF_PICTURE_SECONDS, 0),
            }
            if current
            else {}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), suggested
            ),
            errors=errors,
        )

    # ---- PC screens ----

    async def async_step_add_pc_screen(self, user_input=None):
        return await self._pc_screen_form("add_pc_screen", None, user_input)

    async def async_step_pc_screen(self, user_input=None):
        return await self._pc_screen_form("pc_screen", self._screen, user_input)

    async def _pc_screen_form(self, step_id: str, current: str | None, user_input):
        options = self._options()
        playlists = options[CONF_PLAYLISTS]
        screens = options[CONF_SCREENS]
        if not playlists:
            return self.async_abort(reason="no_playlists")
        errors: dict[str, str] = {}
        if user_input is not None:
            screen_id = user_input[CONF_SCREEN_ID].strip()
            if current and user_input.get(CONF_DELETE):
                screens.pop(current, None)
                return self.async_create_entry(data=options)
            if not re.fullmatch(r"[a-z0-9_]+", screen_id):
                errors[CONF_SCREEN_ID] = "bad_screen_id"
            elif screen_id != current and screen_id in screens:
                errors[CONF_SCREEN_ID] = "screen_exists"
            else:
                if current and screen_id != current:
                    screens.pop(current, None)
                screens[screen_id] = {
                    CONF_KIND: KIND_PC,
                    CONF_NAME: user_input[CONF_NAME].strip() or screen_id,
                    CONF_PLAYLIST: user_input[CONF_PLAYLIST],
                    CONF_PICTURE_SECONDS: int(user_input.get(CONF_PICTURE_SECONDS) or 0),
                    **_schedule_from_input(user_input),
                }
                return self.async_create_entry(data=options)

        existing = screens.get(current, {}) if current else {}
        schema = {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required(CONF_SCREEN_ID): TextSelector(),
            vol.Required(CONF_PLAYLIST): SelectSelector(
                SelectSelectorConfig(
                    options=sorted(playlists, key=str.lower),
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_PICTURE_SECONDS, default=0): SECONDS_OR_ZERO,
            **_schedule_schema(),
        }
        if current:
            schema[vol.Optional(CONF_DELETE, default=False)] = BooleanSelector()
        suggested = user_input or (
            {
                **_schedule_suggested(existing),
                CONF_NAME: existing.get(CONF_NAME),
                CONF_SCREEN_ID: current,
                CONF_PLAYLIST: existing.get(CONF_PLAYLIST),
                CONF_PICTURE_SECONDS: existing.get(CONF_PICTURE_SECONDS, 0),
            }
            if current
            else {}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), suggested
            ),
            errors=errors,
        )

    # ---- default schedule ----

    async def async_step_default_schedule(self, user_input=None):
        options = self._options()
        current = options.get(CONF_DEFAULT_SCHEDULE) or {}
        errors: dict[str, str] = {}
        if user_input is not None:
            times = _times(user_input)
            if times["start"] == times["end"]:
                errors[CONF_END] = "same_times"
            else:
                options[CONF_DEFAULT_SCHEDULE] = {
                    **times,
                    "workday_entity": user_input.get(CONF_WORKDAY_ENTITY) or None,
                }
                return self.async_create_entry(data=options)
        schema = vol.Schema(
            {
                vol.Optional(CONF_DAYS, default=DAYS[:5]): _days_selector(),
                vol.Optional(CONF_START, default="08:30:00"): TimeSelector(),
                vol.Optional(CONF_END, default="18:00:00"): TimeSelector(),
                vol.Optional(CONF_KEEP_ON, default=False): BooleanSelector(),
                vol.Optional(CONF_WORKDAY_ENTITY): WORKDAY_SELECTOR,
            }
        )
        suggested = user_input or {
            **_times_suggested(current),
            **({CONF_WORKDAY_ENTITY: current["workday_entity"]} if current.get("workday_entity") else {}),
        }
        return self.async_show_form(
            step_id="default_schedule",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )
