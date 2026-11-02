"""Opening hours: start and stop each screen (and its TV) on time.

There is a default schedule (days, start, end, "keep on", an optional
workday entity) and each screen uses it, has its own, or has none (started
and stopped by hand). A screen can also be disabled: then it is stopped,
its TV powered off, and the schedule leaves it alone.

An end before the start runs past midnight. The workday entity is any on/off
entity, for example a Workday sensor for the country, so public holidays are
skipped. The screen's power entity is turned on at the start (then a wait,
then the volume) and off at the end.

It acts on changes only: at the start time the screen starts, at the end it
stops; a screen stopped by hand stays stopped until the next start. With
"keep on", once a minute during the hours a stopped screen is started again
(and its TV powered on), and a Cast TV that has left the slideshow (the
Chromecast went back to its home screen, or another app) on two checks in a
row has its playlist restarted. When Home Assistant starts inside the hours,
screens are started (never stopped). The last decision per screen is kept
across reloads, so saving a setting doesn't start or stop anything by itself.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEFAULT_SCHEDULE,
    CONF_ENABLED,
    CONF_POWER_ENTITY,
    CONF_SCHEDULE,
    CONF_START_VOLUME,
    CONF_WORKDAY_ENTITY,
    DOMAIN,
    MODE_DEFAULT,
    MODE_NONE,
    MODE_OWN,
    POWER_ON_WAIT,
)

_LOGGER = logging.getLogger(__name__)
DATA_LAST = f"{DOMAIN}_schedule_last"  # screen id: True (on) / False (off)
DATA_SWITCHING = f"{DOMAIN}_switching"  # screen id: task powering it on/off
CAST_APP = "Default Media Receiver"
DEFAULT = {"days": [0, 1, 2, 3, 4], "start": "08:30", "end": "18:00", "keep_on": False}
NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def default_schedule(options) -> dict:
    return {**DEFAULT, "workday_entity": None, **(options.get(CONF_DEFAULT_SCHEDULE) or {})}


def screen_mode(screen: dict) -> str:
    schedule = screen.get(CONF_SCHEDULE) or {}
    if "mode" in schedule:
        return schedule["mode"]
    return MODE_OWN if schedule.get("enabled") else MODE_NONE  # 0.4 settings


def effective(options, screen: dict) -> dict | None:
    """The schedule a screen follows (with its workday entity), or None."""
    mode = screen_mode(screen)
    if mode == MODE_DEFAULT:
        return default_schedule(options)
    if mode == MODE_OWN:
        return {**DEFAULT, **(screen.get(CONF_SCHEDULE) or {}),
                "workday_entity": screen.get(CONF_WORKDAY_ENTITY)}
    return None


def _time(value: str) -> time:
    parts = [int(p) for p in str(value).split(":")]
    return time(parts[0], parts[1] if len(parts) > 1 else 0)


def in_hours(hass: HomeAssistant, schedule: dict, now: datetime) -> bool:
    days = set(schedule.get("days", []))
    start, end = _time(schedule["start"]), _time(schedule["end"])
    clock = now.time()
    if start <= end:
        on = now.weekday() in days and start <= clock < end
    else:  # past midnight: belongs to the day it started
        on = (now.weekday() in days and clock >= start) or (
            (now - timedelta(days=1)).weekday() in days and clock < end
        )
    if on and (workday := schedule.get("workday_entity")):
        state = hass.states.get(workday)
        on = state is not None and state.state == "on"
    return on


def workday_known(hass: HomeAssistant, schedule: dict) -> bool:
    """False while the workday entity isn't loaded yet (Home Assistant starting)."""
    if not (workday := schedule.get("workday_entity")):
        return True
    state = hass.states.get(workday)
    return state is not None and state.state in ("on", "off")


def wants_on(hass: HomeAssistant, options, screen: dict, now: datetime) -> bool | None:
    """On/off the schedule wants now; None = no schedule (or disabled)."""
    if not screen.get(CONF_ENABLED, True):
        return None
    schedule = effective(options, screen)
    return None if schedule is None else in_hours(hass, schedule, now)


def describe(schedule: dict | None) -> str:
    """Short text, for example "Mon–Fri 08:30–18:00"."""
    if schedule is None:
        return "No schedule"
    days = sorted(set(schedule.get("days", [])))
    if days == list(range(7)):
        text = "Every day"
    elif days and days == list(range(days[0], days[-1] + 1)) and len(days) > 2:
        text = f"{NAMES[days[0]]}–{NAMES[days[-1]]}"
    else:
        text = ", ".join(NAMES[d] for d in days) or "No days"
    return f"{text} {str(schedule.get('start', ''))[:5]}–{str(schedule.get('end', ''))[:5]}"


def _players(hass: HomeAssistant) -> dict:
    """The current players (also while the entry is still being set up)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        players = getattr(entry, "runtime_data", None)
        if isinstance(players, dict):
            return players
    return {}


@callback
def async_switch_screen(hass: HomeAssistant, screen_id: str, on: bool, *, power: bool = True) -> None:
    """Start (power on, volume, playlist) or stop (playlist, power off) a screen."""
    switching = hass.data.setdefault(DATA_SWITCHING, {})
    if task := switching.pop(screen_id, None):
        task.cancel()
    switching[screen_id] = hass.async_create_background_task(
        _async_switch(hass, screen_id, on, power), f"{DOMAIN} switch {screen_id}"
    )


async def _service(hass, domain: str, service: str, entity_id: str, **data) -> None:
    try:
        await hass.services.async_call(
            domain, service, {"entity_id": entity_id, **data}, blocking=True
        )
    except Exception as err:  # noqa: BLE001 - a TV that doesn't answer must not stop the rest
        _LOGGER.warning("%s.%s on %s failed: %s", domain, service, entity_id, err)


async def _async_switch(hass: HomeAssistant, screen_id: str, on: bool, power: bool) -> None:
    from . import DATA_RUNNING
    from .player import ScreenPlayer

    def player():  # looked up each time: a settings change reloads the players
        return _players(hass).get(screen_id)

    running = hass.data.setdefault(DATA_RUNNING, set())
    try:
        current = player()
        if current is None:
            _LOGGER.warning("Can't %s %s: no such screen", "start" if on else "stop", screen_id)
            return
        screen = current.screen
        power_entity = screen.get(CONF_POWER_ENTITY) if power else None
        if on:
            if power_entity:
                await _service(hass, "homeassistant", "turn_on", power_entity)
                await asyncio.sleep(POWER_ON_WAIT)
            volume = screen.get(CONF_START_VOLUME)
            if volume is not None and volume != "":
                target = (
                    power_entity
                    if power_entity and power_entity.startswith("media_player.")
                    else screen.get("media_player")
                )
                if target and _supports_volume(hass, target):
                    await _service(hass, "media_player", "volume_set", target, volume_level=int(volume) / 100)
            current = player()
            if isinstance(current, ScreenPlayer):
                running.add(screen_id)
                current.start()
        else:
            if isinstance(current, ScreenPlayer):
                running.discard(screen_id)
                current.stop()
            if power_entity:
                await _service(hass, "homeassistant", "turn_off", power_entity)
    finally:
        switching = hass.data.get(DATA_SWITCHING, {})
        if switching.get(screen_id) is asyncio.current_task():
            del switching[screen_id]


def _supports_volume(hass: HomeAssistant, entity_id: str) -> bool:
    from homeassistant.components.media_player import MediaPlayerEntityFeature

    state = hass.states.get(entity_id)
    features = state.attributes.get("supported_features", 0) if state else 0
    return bool(features & MediaPlayerEntityFeature.VOLUME_SET)


class Scheduler:
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self._unsubs: list = []
        self._strikes: dict[str, int] = {}  # Cast TVs seen off the slideshow, in a row

    @property
    def _last(self) -> dict[str, bool]:
        return self.hass.data.setdefault(DATA_LAST, {})

    async def async_start(self) -> None:
        self._unsubs.append(async_track_time_change(self.hass, self._tick, second=0))
        workdays = {default_schedule(self.entry.options).get("workday_entity")}
        workdays |= {p.screen.get(CONF_WORKDAY_ENTITY) for p in self.entry.runtime_data.values()}
        workdays.discard(None)
        if workdays:
            self._unsubs.append(
                async_track_state_change_event(self.hass, list(workdays), self._tick)
            )
        self._evaluate()

    def stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _tick(self, *_args) -> None:
        self._evaluate()
        self._keep_on()

    @callback
    def _evaluate(self) -> None:
        now = dt_util.now()
        for screen_id, player in self.entry.runtime_data.items():
            want = wants_on(self.hass, self.entry.options, player.screen, now)
            if want is None:
                self._last.pop(screen_id, None)
                continue
            if not workday_known(self.hass, effective(self.entry.options, player.screen)):
                continue  # decide once the workday entity has loaded
            last = self._last.get(screen_id)
            self._last[screen_id] = want
            if last == want or (last is None and not want):
                continue  # no change (and never switch off just because HA started)
            _LOGGER.info("Schedule: %s %s", screen_id, "start" if want else "stop")
            async_switch_screen(self.hass, screen_id, want)

    @callback
    def _keep_on(self) -> None:
        from .player import ScreenPlayer

        switching = self.hass.data.get(DATA_SWITCHING, {})
        now = dt_util.now()
        for screen_id, player in self.entry.runtime_data.items():
            schedule = effective(self.entry.options, player.screen)
            if (
                not player.screen.get(CONF_ENABLED, True)
                or not schedule
                or not schedule.get("keep_on")
                or not in_hours(self.hass, schedule, now)
            ):
                self._strikes.pop(screen_id, None)
                continue
            if screen_id in switching:
                continue
            power = player.screen.get(CONF_POWER_ENTITY)
            power_state = self.hass.states.get(power) if power else None
            problem = None
            if power_state is not None and power_state.state == "off":
                problem = f"{power} is off"
            elif isinstance(player, ScreenPlayer):
                if not player.running:
                    problem = "stopped"
                else:
                    cast = self.hass.states.get(player.screen.get("media_player", ""))
                    off_slideshow = cast is not None and (
                        cast.state in ("off", "idle", "standby")
                        or cast.attributes.get("app_name") not in (None, CAST_APP)
                    )
                    self._strikes[screen_id] = self._strikes.get(screen_id, 0) + 1 if off_slideshow else 0
                    if self._strikes[screen_id] >= 2:
                        problem = f"left the slideshow ({cast.state}, {cast.attributes.get('app_name')})"
            if problem:
                _LOGGER.warning("Keep on: %s %s, starting it again", screen_id, problem)
                self._strikes.pop(screen_id, None)
                async_switch_screen(self.hass, screen_id, True)


@callback
def async_set_enabled(hass: HomeAssistant, entry, screen_id: str, enabled: bool) -> None:
    """Enable (follow the schedule, starting now if in its hours) or disable a screen."""
    import copy

    options = copy.deepcopy(dict(entry.options))
    screen = options["screens"][screen_id]
    screen[CONF_ENABLED] = enabled
    last = hass.data.setdefault(DATA_LAST, {})
    if enabled:
        want = wants_on(hass, options, screen, dt_util.now())
        if want is None or want:  # no schedule: start by hand = start now
            async_switch_screen(hass, screen_id, True)
        if want is not None:
            last[screen_id] = want
    else:
        last.pop(screen_id, None)
        async_switch_screen(hass, screen_id, False)
    hass.config_entries.async_update_entry(entry, options=options)
