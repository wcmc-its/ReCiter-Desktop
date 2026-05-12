"""Shared-secret API token (per #16).

Local-only desktop app, no remote network exposure. CORS already limits
origins to localhost; this layer adds a per-install secret so that other
localhost-served pages (other dev servers, opened HTML files, browser
extensions running from a localhost context) cannot drive-by call the
API without the user's consent.

The token is generated on first start and persisted to
~/.reciter-desktop/api-token (mode 600). The Next.js shell reads the
same file server-side and surfaces it to the browser bundle through a
same-origin route handler, so attacker pages on other localhost ports
cannot read the token under the browser's same-origin policy.
"""
from __future__ import annotations

import logging
import os
import secrets
import stat
from pathlib import Path

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-Reciter-Token"
TOKEN_PATH = Path.home() / ".reciter-desktop" / "api-token"

# Paths exempt from the token check. /api/health is the liveness probe;
# /api-auth/* is reserved for the Next.js shell to read the token over a
# same-origin route. (FastAPI does not serve /api-auth itself.)
EXEMPT_PATHS = {"/api/health"}

_cached_token: str | None = None


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def load_or_create_token(path: Path = TOKEN_PATH) -> str:
    """Read the token from disk, or generate + persist one on first start."""
    global _cached_token
    if _cached_token is not None:
        return _cached_token

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            _cached_token = token
            return token

    token = _generate_token()
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Best-effort: filesystems that don't support chmod (e.g. some
        # mounted volumes) shouldn't block API startup.
        logger.warning("Could not chmod %s to 0600", path)
    _cached_token = token
    logger.info("Generated new API token at %s", path)
    return token


def reset_cache_for_tests() -> None:
    """Test-only helper to force a re-read from disk."""
    global _cached_token
    _cached_token = None


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry the shared secret in X-Reciter-Token.

    OPTIONS requests pass through unchecked so that CORS preflight can
    answer without the browser ever sending the custom header.
    """

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        provided = request.headers.get(TOKEN_HEADER)
        if not provided or not secrets.compare_digest(provided, self._token):
            return JSONResponse(
                {"detail": "Missing or invalid API token"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return await call_next(request)
