"""Small HTTP helpers shared by the network-backed providers."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import aiohttp

from ..const import PROVIDER_TIMEOUT_SECONDS
from .base import ProviderConnectionError, ProviderResponseError

if TYPE_CHECKING:
    from aiohttp import ClientSession

HTTP_OK = 200
HTTP_REQUEST_TIMEOUT = 408
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500
RESPONSE_PREVIEW_CHARS = 60


async def fetch_text(session: ClientSession | None, url: str) -> str:
    """
    GET ``url`` and return the body as text.

    Raises:
        ProviderConnectionError: On network errors, timeouts and 5xx/408/429.
        ProviderResponseError: On any other non-200 status.
    """
    if session is None:
        msg = "No HTTP session available"
        raise ProviderConnectionError(msg)
    try:
        async with asyncio.timeout(PROVIDER_TIMEOUT_SECONDS):
            async with session.get(url) as response:
                status = response.status
                text = await response.text()
    except TimeoutError as err:
        msg = f"{url} timed out after {PROVIDER_TIMEOUT_SECONDS} s"
        raise ProviderConnectionError(msg) from err
    except aiohttp.ClientError as err:
        msg = f"Failed to connect to {url}: {err}"
        raise ProviderConnectionError(msg) from err

    if status >= HTTP_SERVER_ERROR or status in (
        HTTP_REQUEST_TIMEOUT,
        HTTP_TOO_MANY_REQUESTS,
    ):
        msg = f"{url} returned HTTP {status}"
        raise ProviderConnectionError(msg)
    if status != HTTP_OK:
        msg = f"{url} returned HTTP {status}"
        raise ProviderResponseError(msg)
    return text


async def fetch_json(session: ClientSession | None, url: str) -> Any:
    """
    GET ``url`` and parse the body as JSON, whatever the content type says.

    A dead API that serves an HTML page with HTTP 200 (what islamireland.ie
    does now) therefore surfaces as a clear ProviderResponseError.
    """
    text = await fetch_text(session, url)
    try:
        return json.loads(text)
    except ValueError as err:
        preview = text.strip()[:RESPONSE_PREVIEW_CHARS]
        msg = f"{url} did not return JSON (response starts with {preview!r})"
        raise ProviderResponseError(msg) from err
