"""Cliente HTTP educado: respeita robots.txt, identifica o bot e espaça requisições por host."""

import asyncio
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx


class BlockedByRobots(Exception):
    pass


class PoliteFetcher:
    def __init__(self, user_agent: str, delay_seconds: float, client: httpx.AsyncClient | None = None) -> None:
        self._ua = user_agent
        self._delay = delay_seconds
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": user_agent}, timeout=20, follow_redirects=True
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._last_hit: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _robots_for(self, origin: str) -> RobotFileParser:
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                resp = await self._client.get(f"{origin}/robots.txt")
                parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            except httpx.HTTPError:
                parser.parse([])
            self._robots[origin] = parser
        return self._robots[origin]

    async def get(self, url: str) -> str:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots = await self._robots_for(origin)
        if not robots.can_fetch(self._ua, url):
            raise BlockedByRobots(url)
        lock = self._locks.setdefault(origin, asyncio.Lock())
        async with lock:
            wait = self._last_hit.get(origin, 0) + self._delay - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                resp = await self._client.get(url)
            finally:
                self._last_hit[origin] = time.monotonic()
        resp.raise_for_status()
        return resp.text

    async def aclose(self) -> None:
        await self._client.aclose()
