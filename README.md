# Signage (ha_signage)

A Home Assistant custom integration that turns TVs into digital signage:
playlists of pictures and videos from Home Assistant's media folder, played on
Chromecast TVs or on a PC, with opening hours. Everyone, including non-admin
users, manages it from a **Signage** page in the sidebar.

## What it does

- **Playlists**: pick files from `/media`, set how long pictures stay up, and
  shuffle. Upload pictures and videos (up to 1 GB, with progress) from the
  page.
- **Screens**:
  - **Cast TVs**: Home Assistant casts each file in turn, with its title and
    a thumbnail.
  - **PCs**: they run the agent in `pc-agent/`, which gets the playlist over
    MQTT, downloads the files and plays them with mpv.
  - Each screen follows one playlist and can override the picture time.
- **Schedule**:
  - a default schedule (days, hours, an optional workday entity so public
    holidays are skipped in any country) or a screen's own hours, or none;
  - powers the TV on and off through any entity;
  - **Keep it on** restarts a screen that was switched off or left the
    slideshow, for example a Chromecast that dropped back to its home screen.
- **Entities per screen**:
  - `switch.<screen>_signage` turns the screen on or off;
  - `select.<screen>_playlist` picks its playlist;
  - `media_player.<screen>_signage` shows the playlist, title and picture,
    with play, pause, next and previous. Put it first in a universal media
    player's children so your TV card shows it.

## Install

1. Copy `custom_components/ha_signage` into `/config/custom_components/`
   (or add this repository to HACS as a custom repository).
2. Restart Home Assistant, then add **Signage** under
   Settings > Devices & services. Add playlists and screens under
   **Configure**.
3. Optional, PC screens: install `pc-agent/` on the PC (Python 3 and
   paho-mqtt). Set it up as follows:
   - copy `signage.conf.example` to `/etc/showroom/signage.conf` and set
     `SCREEN_ID` to the screen's id;
   - put the MQTT password in the file that `MQTT_PASSWORD_FILE` points to;
   - enable `showroom-signage-agent.service` as a user unit.

   `showroom-slideshow` is the mpv player the agent drives.

Requires ffmpeg in Home Assistant (it is there in Home Assistant OS) for video
lengths and thumbnails.
