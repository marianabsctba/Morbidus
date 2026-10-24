"""Cliente HTTP educado: respeita robots.txt, identifica o bot e espaça requisições por host."""

import asyncio
import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)

# Falhas que costumam passar sozinhas: rede instável ou o site pedindo calma.
_ERROS_TRANSITORIOS = (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError)
_STATUS_TRANSITORIOS = {429, 500, 502, 503, 504}


class BlockedByRobots(Exception):
    pass


def _decode(resp: httpx.Response) -> str:
    # Sites antigos (ASP.NET, CMS próprios) servem Latin-1 sem declarar charset.
    if "charset" in resp.headers.get("content-type", "").lower():
        return resp.text
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("cp1252", errors="replace")


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        return None


class PoliteFetcher:
    def __init__(
        self,
        user_agent: str,
        delay_seconds: float,
        client: httpx.AsyncClient | None = None,
        tentativas: int = 4,
        espera_maxima: float = 300,
    ) -> None:
        self._ua = user_agent
        self._delay = delay_seconds
        self._tentativas = tentativas
        self._espera_maxima = espera_maxima
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": user_agent}, timeout=20, follow_redirects=True
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._last_hit: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _espera(self, tentativa: int, sugerida: float | None = None) -> float:
        # Cresce rápido (delay x 3, x 9, x 27) para dar tempo de um limite temporário expirar.
        base = sugerida if sugerida is not None else self._delay * 3 ** (tentativa + 1)
        return min(base, self._espera_maxima)

    async def _pedir(self, origin: str, url: str) -> httpx.Response:
        """Uma requisição respeitando o intervalo por host, com novas tentativas em falhas passageiras."""
        lock = self._locks.setdefault(origin, asyncio.Lock())
        for tentativa in range(self._tentativas):
            async with lock:
                wait = self._last_hit.get(origin, 0) + self._delay - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    resp = await self._client.get(url)
                except _ERROS_TRANSITORIOS as exc:
                    erro, resp = exc, None
                finally:
                    self._last_hit[origin] = time.monotonic()
            ultima = tentativa == self._tentativas - 1
            if resp is not None and resp.status_code not in _STATUS_TRANSITORIOS:
                return resp
            if ultima:
                if resp is None:
                    raise erro
                return resp
            espera = self._espera(tentativa, _retry_after(resp) if resp is not None else None)
            motivo = f"HTTP {resp.status_code}" if resp is not None else type(erro).__name__
            log.warning("%s em %s; nova tentativa em %.0fs", motivo, url, espera)
            await asyncio.sleep(espera)
        raise AssertionError("inalcançável")

    async def _robots_for(self, origin: str) -> RobotFileParser:
        if origin not in self._robots:
            parser = RobotFileParser()
            resp = await self._pedir(origin, f"{origin}/robots.txt")
            if resp.status_code >= 500:
                # RFC 9309: robots inacessível por erro do servidor equivale a "proibido".
                raise BlockedByRobots(f"{origin}/robots.txt respondeu {resp.status_code}")
            parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            self._robots[origin] = parser
        return self._robots[origin]

    async def get(self, url: str) -> str:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots = await self._robots_for(origin)
        if not robots.can_fetch(self._ua, url):
            raise BlockedByRobots(url)
        resp = await self._pedir(origin, url)
        resp.raise_for_status()
        return _decode(resp)

    async def aclose(self) -> None:
        await self._client.aclose()
