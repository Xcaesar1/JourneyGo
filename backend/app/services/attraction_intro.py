"""Short, attributed encyclopedia extracts; never generated attraction facts."""

import asyncio
import re
import time
from collections import OrderedDict

import httpx

_cache: OrderedDict[tuple[str, str], tuple[float, dict]] = OrderedDict()
_limit = asyncio.Semaphore(3)
_API = "https://zh.wikipedia.org/w/api.php"


def short_intro(text: str) -> str:
    text = re.sub(r"（[^）]*）|\([^)]*\)|\[[^]]*\]", "", text)
    text = re.sub(r"\s+", "", text).strip()
    if len(text) <= 30:
        return text
    for index in range(28, 19, -1):
        if text[index] in "，。；：":
            return text[:index] + "。"
    return text[:29] + "…"


async def get_attraction_intro(name: str, city: str) -> dict:
    name, city = name.strip(), city.strip().removesuffix("市")
    if not name or not city:
        return {}
    key = (name, city)
    async with _limit:
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            _cache.move_to_end(key)
            return cached[1]
        result = {}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(_API, params={
                    "action": "query", "prop": "extracts|info|pageprops",
                    "inprop": "url", "exintro": "1", "explaintext": "1",
                    "redirects": "1", "titles": name, "format": "json",
                    "formatversion": "2", "variant": "zh-cn",
                }, headers={"User-Agent": "JourneyGo/1.0 (https://github.com/Xcaesar1/JourneyGo)"})
                response.raise_for_status()
                for page in response.json().get("query", {}).get("pages", []):
                    extract = page.get("extract", "")
                    url = page.get("fullurl", "")
                    # Exact-title lookup may follow redirects, but city must still match.
                    if (page.get("missing") or "disambiguation" in page.get("pageprops", {})
                            or city not in extract or not url.startswith("https://zh.wikipedia.org/wiki/")):
                        continue
                    summary = short_intro(extract)
                    if summary:
                        result = {"summary": summary, "source_url": url,
                                  "source": "Wikipedia", "license": "CC BY-SA 4.0",
                                  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}
                    break
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
        _cache[key] = (time.monotonic() + (86400 if result else 300), result)
        _cache.move_to_end(key)
        while len(_cache) > 512:
            _cache.popitem(last=False)
        return result
