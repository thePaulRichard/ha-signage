"""Constants for Signage."""

DOMAIN = "ha_signage"
PLATFORMS = ["switch", "select", "media_player"]

CONF_PLAYLISTS = "playlists"
CONF_SCREENS = "screens"
CONF_FILES = "files"
CONF_PICTURE_SECONDS = "picture_seconds"
CONF_SHUFFLE = "shuffle"
CONF_MEDIA_PLAYER = "media_player"
CONF_PLAYLIST = "playlist"
CONF_NAME = "name"
CONF_KIND = "kind"
KIND_CAST = "cast"  # a Cast TV: Home Assistant casts each file in turn
KIND_PC = "pc"  # a PC running the signage agent: it gets the playlist over MQTT

# schedule (per screen)
CONF_ENABLED = "enabled"  # screen on/off: off = stopped, powered off, schedule ignored
CONF_SCHEDULE = "schedule"  # {"mode": "default"|"own"|"none", "days": [0..6, Monday = 0], "start": "HH:MM", "end": "HH:MM", "keep_on": bool}
CONF_DEFAULT_SCHEDULE = "default_schedule"  # {"days", "start", "end", "keep_on", "workday_entity"}
CONF_WORKDAY_ENTITY = "workday_entity"  # optional on/off entity: only run while it is on
MODE_DEFAULT, MODE_OWN, MODE_NONE = "default", "own", "none"
CONF_POWER_ENTITY = "power_entity"  # optional: turned on at the start, off at the end
CONF_START_VOLUME = "start_volume"  # optional 0-100, set after powering on
POWER_ON_WAIT = 15  # seconds between powering a TV on and starting its playlist
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

MQTT_PREFIX = "ha_signage"
PC_URL_DAYS = 7  # download links sent to PCs last this long
PC_REPUBLISH_HOURS = 12  # and are renewed this often

DEFAULT_PICTURE_SECONDS = 150

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}

THUMB_URL = "/api/ha_signage/thumb/{key}"


def signal_screen_update(screen_id: str) -> str:
    """Dispatcher signal sent when a screen starts, stops or shows a new file."""
    return f"{DOMAIN}_update_{screen_id}"
