"""The media library: the files in Home Assistant's local media folder.

For each file it works out, once, whether it is a picture or a video, how
long a video lasts, and a small thumbnail for the media cards (ffmpeg, which
ships with Home Assistant). The results are cached by file size and time.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, IMAGE_EXTENSIONS, THUMB_URL, VIDEO_EXTENSIONS

_LOGGER = logging.getLogger(__name__)
_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_THUMB_NAME = re.compile(r"[0-9a-f]{16}\.jpg")


class MediaLibrary:
    """Files under the local media folder, with their length and thumbnail."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.root = Path(hass.config.media_dirs.get("local", "/media"))
        self.thumb_dir = Path(hass.config.path(DOMAIN, "thumbs"))
        self.ffmpeg = shutil.which("ffmpeg")
        self._store: Store = Store(hass, 1, f"{DOMAIN}.media")
        self._cache: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        if self.ffmpeg is None:
            _LOGGER.warning("ffmpeg not found: no thumbnails, video lengths from the TVs")

    async def async_load(self) -> None:
        """Load the cache and make sure the thumbnail folder exists."""
        self._cache = await self._store.async_load() or {}
        await self.hass.async_add_executor_job(
            lambda: self.thumb_dir.mkdir(parents=True, exist_ok=True)
        )

    def _list_files(self) -> list[str]:
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in filenames:
                if name.startswith("."):
                    continue
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                    files.append(
                        str(Path(dirpath, name).relative_to(self.root).as_posix())
                    )
        return sorted(files, key=str.lower)

    async def async_files(self) -> list[str]:
        """Pictures and videos in the media folder, as paths relative to it."""
        return await self.hass.async_add_executor_job(self._list_files)

    @staticmethod
    def kind(rel: str) -> str:
        """"video" or "image"."""
        return "video" if Path(rel).suffix.lower() in VIDEO_EXTENSIONS else "image"

    @staticmethod
    def title(rel: str) -> str:
        """The file name without folder and extension."""
        return Path(rel).stem

    async def async_info(self, rel: str) -> dict | None:
        """Kind, duration (videos, seconds) and thumbnail key; None if missing."""
        path = self.root / rel
        try:
            stat = await self.hass.async_add_executor_job(path.stat)
        except OSError:
            return None
        sig = f"{stat.st_mtime_ns}-{stat.st_size}"
        lock = self._locks.setdefault(rel, asyncio.Lock())
        async with lock:
            cached = self._cache.get(rel)
            if cached and cached.get("sig") == sig:
                return cached
            kind = self.kind(rel)
            duration = await self._probe_duration(path) if kind == "video" else None
            key = hashlib.sha1(f"{rel}|{sig}".encode()).hexdigest()[:16]
            thumb = await self._make_thumb(path, kind, duration, key)
            info = {"sig": sig, "kind": kind, "duration": duration, "thumb": thumb}
            self._cache[rel] = info
            self._store.async_delay_save(lambda: self._cache, 10)
            return info

    async def _ffmpeg(self, *args: str) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            self.ffmpeg,
            "-hide_banner",
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(60):
                _, err = await proc.communicate()
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, ""
        return proc.returncode, err.decode(errors="replace")

    async def _probe_duration(self, path: Path) -> float | None:
        if self.ffmpeg is None:
            return None
        _, err = await self._ffmpeg("-i", str(path))
        if match := _DURATION.search(err):
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        _LOGGER.warning("Could not read the length of %s", path)
        return None

    async def _make_thumb(
        self, path: Path, kind: str, duration: float | None, key: str
    ) -> str | None:
        if self.ffmpeg is None:
            return None
        target = self.thumb_dir / f"{key}.jpg"
        if await self.hass.async_add_executor_job(target.is_file):
            return key
        seek = []
        if kind == "video":
            seek = ["-ss", f"{min(3.0, (duration or 0) / 2):.1f}"]
        code, err = await self._ffmpeg(
            "-y", "-loglevel", "error", *seek, "-i", str(path), "-frames:v", "1",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease",
            "-q:v", "4", str(target),
        )
        if code != 0:
            _LOGGER.warning("Could not make a thumbnail of %s: %s", path, err.strip())
            return None
        return key


class ThumbnailView(HomeAssistantView):
    """Serves the thumbnails (to signed URLs, so the media cards can load them)."""

    url = THUMB_URL
    name = f"api:{DOMAIN}:thumb"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, thumb_dir: Path) -> None:
        self.hass = hass
        self.thumb_dir = thumb_dir

    async def get(self, request: web.Request, key: str) -> web.FileResponse:
        if not _THUMB_NAME.fullmatch(key):
            raise web.HTTPNotFound
        path = self.thumb_dir / key
        if not await self.hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})
