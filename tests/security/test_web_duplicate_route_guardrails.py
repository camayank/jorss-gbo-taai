"""Guardrails against duplicate launch-sensitive web routes."""

from __future__ import annotations

import os
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Tuple

from fastapi.routing import APIRoute


LAUNCH_SENSITIVE_PREFIXES = (
    "/api/returns",
    "/api/upload",
    "/api/documents",
    "/api/calculate",
    "/api/optimize",
)


@lru_cache(maxsize=1)
def _load_web_app():
    """
    Load the web app once for route inspection.

    Matplotlib cache path is redirected to avoid slow first-run cache writes
    in restricted environments during test collection.
    """
    os.environ.setdefault("MPLCONFIGDIR", "/tmp")
    from web.app import app

    return app


def _collect_launch_route_map() -> Dict[Tuple[str, str], List[dict]]:
    """
    Build {(METHOD, PATH): [auth metadata...]} for launch-sensitive route families.
    """
    app = _load_web_app()
    route_map: Dict[Tuple[str, str], List[dict]] = defaultdict(list)

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        if not route.path.startswith(LAUNCH_SENSITIVE_PREFIXES):
            continue

        dep_calls = []
        for dep in route.dependant.dependencies:
            call = getattr(dep, "call", None)
            if call:
                dep_calls.append(
                    f"{getattr(call, '__module__', '?')}.{getattr(call, '__name__', str(call))}"
                )

        metadata = {
            "endpoint": f"{route.endpoint.__module__}.{route.endpoint.__name__}",
            "dependencies": tuple(sorted(dep_calls)),
        }

        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            route_map[(method, route.path)].append(metadata)

    return route_map


def test_launch_route_families_have_no_duplicate_method_path_entries():
    """Critical launch route families must resolve to a single runtime owner."""
    route_map = _collect_launch_route_map()
    duplicates = {key: entries for key, entries in route_map.items() if len(entries) > 1}
    assert not duplicates, f"Duplicate launch-sensitive routes detected: {duplicates}"


def test_no_conflicting_auth_metadata_for_launch_routes():
    """
    Duplicate launch routes with differing auth metadata are blocked in CI.
    """
    route_map = _collect_launch_route_map()
    conflicts = {}

    for route_key, entries in route_map.items():
        if len(entries) < 2:
            continue

        auth_fingerprints = {
            (entry["endpoint"], entry["dependencies"])
            for entry in entries
        }
        if len(auth_fingerprints) > 1:
            conflicts[route_key] = entries

    assert not conflicts, f"Conflicting launch route auth metadata detected: {conflicts}"
