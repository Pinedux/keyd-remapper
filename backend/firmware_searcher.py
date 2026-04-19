"""Firmware search module for QMK/VIAL keyboard firmware."""

import logging
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/firmware", tags=["firmware"])

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
QMK_API_URL = "https://api.qmk.fm/v1/keyboards"

# In-memory cache for QMK keyboard list: (timestamp, data)
_qmk_cache: Optional[tuple[float, List[str]]] = None
_QMK_CACHE_TTL_SECONDS = 300  # 5 minutes


class FirmwareResult(BaseModel):
    name: str
    url: str
    description: str
    source: str
    compatibility: str


class FirmwareSearchResponse(BaseModel):
    query: str
    results: List[FirmwareResult]
    fallback_searched: bool


def _get_qmk_keyboards() -> List[str]:
    """Fetch QMK keyboard list from API with 5-minute in-memory cache."""
    global _qmk_cache
    now = time.time()
    if _qmk_cache is not None and (now - _qmk_cache[0]) < _QMK_CACHE_TTL_SECONDS:
        return _qmk_cache[1]

    try:
        resp = requests.get(QMK_API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        keyboards: List[str] = []
        if isinstance(data, list):
            keyboards = data
        elif isinstance(data, dict):
            keyboards = data.get("keyboards", data.get("data", []))
        _qmk_cache = (now, keyboards)
        return keyboards
    except requests.exceptions.RequestException as exc:
        logger.warning("QMK API request failed: %s", exc)
        return []
    except Exception as exc:
        logger.warning("QMK API unexpected error: %s", exc)
        return []


def _search_qmk_configurator(query: str) -> List[FirmwareResult]:
    """Search QMK Configurator database by substring match."""
    results: List[FirmwareResult] = []
    keyboards = _get_qmk_keyboards()
    if not keyboards:
        return results

    q_lower = query.lower()
    for kb in keyboards:
        kb_lower = kb.lower()
        if q_lower in kb_lower:
            compatibility = "exact" if q_lower == kb_lower else "likely"
            results.append(
                FirmwareResult(
                    name=kb,
                    url=f"https://config.qmk.fm/#/{kb}",
                    description="QMK Configurator supported keyboard",
                    source="qmk-configurator",
                    compatibility=compatibility,
                )
            )
    return results


def _github_search_repos(
    params: Dict[str, Any],
    source_tag: str,
    compatibility: str,
    description_prefix: str = "",
    timeout: int = 15,
) -> List[FirmwareResult]:
    """Generic GitHub repository search helper."""
    results: List[FirmwareResult] = []
    url = f"{GITHUB_API_BASE}/search/repositories"
    try:
        resp = requests.get(
            url,
            params=params,
            timeout=timeout,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 403:
            logger.warning("GitHub API rate limited for %s", source_tag)
            return results
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            name = item.get("name", "unknown")
            full_name = item.get("full_name", "")
            desc = item.get("description") or ""
            if description_prefix:
                desc = f"{description_prefix}: {desc}" if desc else description_prefix
            results.append(
                FirmwareResult(
                    name=name,
                    url=item.get("html_url", ""),
                    description=desc,
                    source=source_tag,
                    compatibility=compatibility,
                )
            )
    except requests.exceptions.RequestException as exc:
        logger.warning("GitHub repo search failed (%s): %s", source_tag, exc)
    except Exception as exc:
        logger.warning("GitHub repo search unexpected error (%s): %s", source_tag, exc)
    return results


def _search_vial_repos(query: str) -> List[FirmwareResult]:
    """Search GitHub for VIAL-related repositories using topics."""
    results: List[FirmwareResult] = []
    seen_names = set()
    searches = [
        {"q": f"topic:vial {query}", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"topic:vial-keyboard {query}", "sort": "stars", "order": "desc", "per_page": 10},
    ]
    for params in searches:
        batch = _github_search_repos(
            params=params,
            source_tag="vial",
            compatibility="likely",
            description_prefix="VIAL firmware",
        )
        for item in batch:
            if item.name not in seen_names:
                seen_names.add(item.name)
                results.append(item)
    return results


def _search_vial_code(query: str) -> List[FirmwareResult]:
    """Search for code inside vial-kb/vial-qmk repo."""
    results: List[FirmwareResult] = []
    url = f"{GITHUB_API_BASE}/search/code"
    try:
        resp = requests.get(
            url,
            params={"q": f"{query} repo:vial-kb/vial-qmk", "per_page": 10},
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 403:
            logger.warning("GitHub API rate limited for vial code search")
            return results
        resp.raise_for_status()
        data = resp.json()
        seen = set()
        for item in data.get("items", []):
            repo = item.get("repository", {})
            repo_name = repo.get("full_name", "vial-kb/vial-qmk")
            name = item.get("name", "unknown")
            key = (repo_name, name)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                FirmwareResult(
                    name=name,
                    url=item.get("html_url", ""),
                    description=f"VIAL firmware file: {name}",
                    source="vial",
                    compatibility="likely",
                )
            )
    except requests.exceptions.RequestException as exc:
        logger.warning("VIAL code search failed: %s", exc)
    except Exception as exc:
        logger.warning("VIAL code search unexpected error: %s", exc)
    return results


def _search_kbfirmware(query: str) -> List[FirmwareResult]:
    """Search GitHub for KBFirmware and keyboard-layout-editor related repos."""
    results: List[FirmwareResult] = []
    seen_names = set()
    searches = [
        {
            "q": f"{query} keyboard-layout-editor",
            "sort": "stars",
            "order": "desc",
            "per_page": 10,
        },
        {"q": f"{query} kbfirmware", "sort": "stars", "order": "desc", "per_page": 10},
    ]
    for params in searches:
        batch = _github_search_repos(
            params=params,
            source_tag="kbfirmware",
            compatibility="likely",
            description_prefix="KB Firmware / layout editor reference",
        )
        for item in batch:
            if item.name not in seen_names:
                seen_names.add(item.name)
                results.append(item)
    return results


def _search_qmk_code(query: str) -> List[FirmwareResult]:
    """Search for code inside qmk/qmk_firmware repo."""
    results: List[FirmwareResult] = []
    url = f"{GITHUB_API_BASE}/search/code"
    try:
        resp = requests.get(
            url,
            params={"q": f"{query} repo:qmk/qmk_firmware", "per_page": 10},
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 403:
            logger.warning("GitHub API rate limited for qmk code search")
            return results
        resp.raise_for_status()
        data = resp.json()
        seen = set()
        for item in data.get("items", []):
            repo = item.get("repository", {})
            repo_name = repo.get("full_name", "qmk/qmk_firmware")
            name = item.get("name", "unknown")
            key = (repo_name, name)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                FirmwareResult(
                    name=name,
                    url=item.get("html_url", ""),
                    description=f"QMK firmware file: {name}",
                    source="qmk",
                    compatibility="likely",
                )
            )
    except requests.exceptions.RequestException as exc:
        logger.warning("QMK code search failed: %s", exc)
    except Exception as exc:
        logger.warning("QMK code search unexpected error: %s", exc)
    return results


def _fallback_github_search(query: str) -> List[FirmwareResult]:
    """Broader GitHub fallback searches when primary sources yield few results."""
    results: List[FirmwareResult] = []
    seen_names = set()
    searches = [
        {"q": f"{query} keyboard firmware", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"{query} qmk keymap", "sort": "stars", "order": "desc", "per_page": 10},
        {"q": f"{query} keymap.c", "sort": "stars", "order": "desc", "per_page": 10},
    ]
    for params in searches:
        batch = _github_search_repos(
            params=params,
            source_tag="github",
            compatibility="generic",
        )
        for item in batch:
            if item.name not in seen_names:
                seen_names.add(item.name)
                results.append(item)
    return results


def _rank_results(results: List[FirmwareResult]) -> List[FirmwareResult]:
    """Sort results: exact first, then likely, then generic."""
    priority = {"exact": 0, "likely": 1, "generic": 2}
    return sorted(results, key=lambda r: priority.get(r.compatibility, 3))


@router.get("/search", response_model=FirmwareSearchResponse)
def search_firmware(q: str = "") -> FirmwareSearchResponse:
    """Search for keyboard firmware across QMK Configurator, VIAL, and GitHub."""
    if not q or len(q) > 100:
        raise HTTPException(status_code=400, detail="Query must be between 1 and 100 characters.")

    all_results: List[FirmwareResult] = []
    seen_urls: set[str] = set()
    fallback_searched = False

    def _add_unique(batch: List[FirmwareResult]) -> None:
        for item in batch:
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                all_results.append(item)

    try:
        _add_unique(_search_qmk_configurator(q))
    except Exception as exc:
        logger.error("QMK configurator search crashed: %s", exc)

    try:
        _add_unique(_search_vial_repos(q))
    except Exception as exc:
        logger.error("VIAL repo search crashed: %s", exc)

    try:
        _add_unique(_search_vial_code(q))
    except Exception as exc:
        logger.error("VIAL code search crashed: %s", exc)

    try:
        _add_unique(_search_kbfirmware(q))
    except Exception as exc:
        logger.error("KB firmware search crashed: %s", exc)

    try:
        _add_unique(_search_qmk_code(q))
    except Exception as exc:
        logger.error("QMK code search crashed: %s", exc)

    if len(all_results) < 3:
        fallback_searched = True
        try:
            _add_unique(_fallback_github_search(q))
        except Exception as exc:
            logger.error("Fallback GitHub search crashed: %s", exc)

    ranked = _rank_results(all_results)
    limited = ranked[:20]

    return FirmwareSearchResponse(
        query=q,
        results=limited,
        fallback_searched=fallback_searched,
    )
