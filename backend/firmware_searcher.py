"""Firmware search module for QMK/VIAL keyboard firmware."""

from typing import List

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/firmware", tags=["firmware"])

GITHUB_API_BASE = "https://api.github.com"


class FirmwareResult(BaseModel):
    name: str
    repo: str
    url: str
    description: str
    source: str


def _search_github_repos(query: str) -> List[FirmwareResult]:
    """Search GitHub repositories for keyboard firmware."""
    results: List[FirmwareResult] = []
    q = f"{query} keyboard firmware"
    url = f"{GITHUB_API_BASE}/search/repositories"
    try:
        resp = requests.get(
            url,
            params={"q": q, "sort": "stars", "order": "desc", "per_page": 10},
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 403:
            # Rate limited
            return results
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            results.append(
                FirmwareResult(
                    name=item.get("name", "unknown"),
                    repo=item.get("full_name", ""),
                    url=item.get("html_url", ""),
                    description=item.get("description") or "",
                    source="github",
                )
            )
    except requests.exceptions.RequestException:
        pass
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
                    repo=repo_name,
                    url=item.get("html_url", ""),
                    description=f"QMK firmware file: {name}",
                    source="qmk",
                )
            )
    except requests.exceptions.RequestException:
        pass
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
                    repo=repo_name,
                    url=item.get("html_url", ""),
                    description=f"VIAL firmware file: {name}",
                    source="vial",
                )
            )
    except requests.exceptions.RequestException:
        pass
    return results


@router.get("/search", response_model=List[FirmwareResult])
def search_firmware(q: str = "") -> List[FirmwareResult]:
    """Search for keyboard firmware on GitHub."""
    if not q or len(q) > 100:
        raise HTTPException(status_code=400, detail="Query must be between 1 and 100 characters.")

    all_results: List[FirmwareResult] = []
    seen_urls = set()

    for batch in [
        _search_github_repos(q),
        _search_qmk_code(q),
        _search_vial_code(q),
    ]:
        for item in batch:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                all_results.append(item)

    return all_results
