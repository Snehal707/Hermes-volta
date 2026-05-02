#!/usr/bin/env python3
"""Hermes Volta component price lookup via search snippets.

This module is intended to run inside Hermes execute_code, where the
`web_search(query, limit=...)` helper is available. It deliberately does not
scrape lcsc.com directly. Prices are inferred only from search result snippets;
if no usable price appears, the caller gets a clear manual-check fallback.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable


PRICE_UNAVAILABLE = "Price unavailable — check lcsc.com manually"


@dataclass(frozen=True)
class SearchHit:
    title: str
    snippet: str
    url: str


@dataclass(frozen=True)
class ComponentPrice:
    value: str
    component_type: str
    footprint: str
    price: str
    price_found: bool
    source_url: str | None
    source_title: str | None
    source_snippet: str | None
    queries: list[str]


def build_queries(value: str, component_type: str = "resistor", footprint: str = "0402") -> list[str]:
    """Build search queries for LCSC/JLCPCB price snippets."""
    part = (component_type or "resistor").strip().lower()
    fp = (footprint or "0402").strip()
    val = normalize_query_value(str(value), part)

    return [
        f"site:lcsc.com {val} {fp} {part} price",
        f"JLCPCB basic parts {val} {fp} price",
        f"{val} {fp} SMD {part} LCSC price 2026",
    ]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def normalize_query_value(value: str, component_type: str = "") -> str:
    """Normalize engineering values into search-friendly text."""
    part = (component_type or "").strip().lower()
    normalized = str(value).strip()
    replacements = {
        "Ω": "ohm",
        "Ω": "ohm",
        "ω": "ohm",
        "Î©": "ohm",
        "Ï‰": "ohm",
        "î©": "ohm",
        "µ": "u",
        "μ": "u",
        "Î¼": "u",
        "Âµ": "u",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"\s+", "", normalized)

    if part == "resistor":
        normalized = re.sub(r"(?i)ohms?$", "", normalized)
    return normalized


def _normalize_results(raw_results: Any) -> list[SearchHit]:
    """Normalize likely web_search/DDGS result shapes into SearchHit objects."""
    if raw_results is None:
        return []

    if isinstance(raw_results, dict):
        for key in ("results", "items", "web", "organic"):
            if isinstance(raw_results.get(key), list):
                raw_results = raw_results[key]
                break
        else:
            raw_results = [raw_results]

    if not isinstance(raw_results, list):
        raw_results = list(raw_results) if isinstance(raw_results, Iterable) and not isinstance(raw_results, str) else []

    hits: list[SearchHit] = []
    for item in raw_results:
        if isinstance(item, str):
            hits.append(SearchHit(title="", snippet=item, url=""))
            continue
        if not isinstance(item, dict):
            continue

        title = _text(item.get("title") or item.get("name"))
        snippet = _text(
            item.get("snippet")
            or item.get("body")
            or item.get("description")
            or item.get("text")
            or item.get("content")
        )
        url = _text(item.get("url") or item.get("href") or item.get("link"))
        hits.append(SearchHit(title=title, snippet=snippet, url=url))

    return hits


def _injected_web_search(query: str, limit: int) -> list[SearchHit]:
    search_fn = globals().get("web_search")
    if not callable(search_fn):
        return []

    try:
        return _normalize_results(search_fn(query, limit=limit))
    except TypeError:
        return _normalize_results(search_fn(query))
    except Exception:
        return []


def _ddgs_search(query: str, limit: int) -> list[SearchHit]:
    """Optional local fallback to a search backend, still snippet-only."""
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except Exception:
            return []

    try:
        with DDGS() as ddgs:
            return _normalize_results(list(ddgs.text(query, max_results=limit)))
    except Exception:
        return []


def run_search(query: str, limit: int = 5) -> list[SearchHit]:
    """Run snippet search, preferring Hermes web_search when available."""
    hits = _injected_web_search(query, limit)
    if hits:
        return hits
    return _ddgs_search(query, limit)


PRICE_PATTERNS = [
    re.compile(r"(?i)\b(?:US\$|USD)\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?<![A-Z])\$\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\b(?:CNY|RMB|CN¥|¥)\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\b(?:INR|Rs\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\bEUR\s*([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\b([0-9]+(?:\.[0-9]+)?)\s*(?:USD|US\$|\$|CNY|RMB|INR|EUR)\b"),
]


def parse_price_from_hits(hits: Iterable[SearchHit]) -> tuple[str | None, SearchHit | None]:
    """Extract the first plausible price from search result snippets."""
    for hit in hits:
        haystack = " ".join(part for part in (hit.title, hit.snippet) if part)
        if not haystack:
            continue

        for pattern in PRICE_PATTERNS:
            match = pattern.search(haystack)
            if match:
                token = match.group(0).strip()
                return token, hit

    return None, None


def search_component_price(
    value: str,
    component_type: str = "resistor",
    footprint: str = "0402",
    limit: int = 5,
    search_func: Callable[[str, int], list[SearchHit]] | None = None,
) -> ComponentPrice:
    """Search for a component price using only web search result snippets."""
    queries = build_queries(value=value, component_type=component_type, footprint=footprint)
    runner = search_func or run_search

    all_hits: list[SearchHit] = []
    for query in queries:
        hits = runner(query, limit)
        all_hits.extend(hits)
        price, source = parse_price_from_hits(hits)
        if price and source:
            return ComponentPrice(
                value=str(value),
                component_type=component_type,
                footprint=footprint,
                price=price,
                price_found=True,
                source_url=source.url or None,
                source_title=source.title or None,
                source_snippet=source.snippet or None,
                queries=queries,
            )

    price, source = parse_price_from_hits(all_hits)
    if price and source:
        return ComponentPrice(
            value=str(value),
            component_type=component_type,
            footprint=footprint,
            price=price,
            price_found=True,
            source_url=source.url or None,
            source_title=source.title or None,
            source_snippet=source.snippet or None,
            queries=queries,
        )

    return ComponentPrice(
        value=str(value),
        component_type=component_type,
        footprint=footprint,
        price=PRICE_UNAVAILABLE,
        price_found=False,
        source_url=None,
        source_title=None,
        source_snippet=None,
        queries=queries,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Search LCSC/JLCPCB price snippets for a BOM component.")
    parser.add_argument("--value", required=True, help="Component value, for example 1.6k, 100nF, 10uH.")
    parser.add_argument("--type", default="resistor", choices=["resistor", "capacitor", "inductor"])
    parser.add_argument("--footprint", default="0402")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = search_component_price(
        value=args.value,
        component_type=args.type,
        footprint=args.footprint,
        limit=max(1, args.limit),
    )

    if args.json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        print(f"{result.component_type.upper()} {result.value} {result.footprint}")
        print(f"Price: {result.price}")
        if result.price_found:
            print(f"Source: {result.source_title or result.source_url or 'search snippet'}")
            if result.source_url:
                print(f"URL: {result.source_url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
