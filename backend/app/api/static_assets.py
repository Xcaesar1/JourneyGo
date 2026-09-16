"""Compression and browser caching for build assets, never API event streams."""

import re

from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles


class BuildAssets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Windows MIME registry entries can incorrectly label JavaScript as text/plain.
        suffix = path.rsplit(".", 1)[-1].lower()
        if response.status_code == 200 and suffix in ("js", "css"):
            response.headers["Content-Type"] = {
                "js": "text/javascript; charset=utf-8",
                "css": "text/css; charset=utf-8",
            }[suffix]
        if response.status_code in (200, 304) and re.search(
            r"-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$", path
        ):
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


def build_assets(directory):
    return GZipMiddleware(BuildAssets(directory=directory), minimum_size=1024, compresslevel=6)
