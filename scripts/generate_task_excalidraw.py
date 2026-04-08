#!/usr/bin/env python3
"""
Generate Excalidraw (.excalidraw) topology diagrams from tasks/multi_turn/*.json.

Usage (from benchmark repo root):
  python scripts/generate_task_excalidraw.py

By default reads task JSON from ~/Documents/papers/mdpi_decentralized_paper/multi_turn
(if that folder exists and contains *.json), else from this repo's tasks/multi_turn.

Writes .excalidraw files to ~/Documents/papers/mdpi_decentralized_paper/multi_turn/excalidraw
by default. Override with --tasks-dir and --output.

Open the .excalidraw files in Excalidraw (desktop, web, or Obsidian plugin).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import secrets
import string
from pathlib import Path
from typing import Any


def _mdpi_multi_turn_root() -> Path:
    return (
        Path.home()
        / "Documents"
        / "papers"
        / "mdpi_decentralized_paper"
        / "multi_turn"
    )


def _default_excalidraw_output() -> Path:
    """Paper-side diagram folder (mdpi_decentralized_paper/multi_turn/excalidraw)."""
    return _mdpi_multi_turn_root() / "excalidraw"


def _default_tasks_dir() -> Path:
    """Prefer MDPI paper multi_turn/ (task JSON next to excalidraw/); else benchmark repo."""
    mdpi = _mdpi_multi_turn_root()
    if mdpi.is_dir() and any(mdpi.glob("*.json")):
        return mdpi
    return Path(__file__).resolve().parent.parent / "tasks" / "multi_turn"


def _eid() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _nonce() -> int:
    return random.randint(1, 2**31 - 1)


# Hand-tuned layouts (canvas px). Centers of router boxes.
_PRESET_POSITIONS: dict[str, dict[str, tuple[float, float]]] = {
    "ccna_rip_routing_basic": {
        "R1": (420, 100),
        "R2": (200, 300),
        "R3": (640, 300),
        "R4": (420, 500),
    },
    "troubleshoot_ospf_adjacency_issue": {
        "R1": (420, 100),
        "R2": (200, 300),
        "R3": (640, 300),
        "R4": (420, 500),
    },
    "ccnp_multiarea_ospf_intermediate": {
        "R1": (420, 80),
        "R2": (200, 260),
        "R3": (640, 260),
        "R4": (200, 480),
        "R5": (640, 480),
    },
    "ccie_bgp_dual_homing_expert": {
        "ISP1": (100, 100),
        "EDGE1": (100, 280),
        "CORE": (420, 280),
        "EDGE2": (740, 280),
        "ISP2": (740, 100),
    },
    "troubleshoot_bgp_route_filtering": {
        "ISP": (420, 100),
        "EDGE": (420, 300),
        "INTERNAL1": (200, 500),
        "INTERNAL2": (640, 500),
    },
}

# Optional large labels (protocol semantics). Drawn as faded rectangles + text.
_REGIONS: dict[str, list[dict[str, Any]]] = {
    "ccnp_multiarea_ospf_intermediate": [
        {
            "label": "Area 0 (backbone): R1-R2-R3 segment",
            "x": 140,
            "y": 40,
            "w": 560,
            "h": 220,
            "fill": "#fff9db",
        },
        {
            "label": "Area 1: R4 stub",
            "x": 100,
            "y": 380,
            "w": 240,
            "h": 200,
            "fill": "#e7f5ff",
        },
        {
            "label": "Area 2: R5 stub",
            "x": 540,
            "y": 380,
            "w": 240,
            "h": 200,
            "fill": "#ebfbee",
        },
    ],
    "ccie_bgp_dual_homing_expert": [
        {
            "label": "AS 65001",
            "x": 40,
            "y": 60,
            "w": 200,
            "h": 340,
            "fill": "#ffe8e8",
        },
        {
            "label": "Enterprise (internal)",
            "x": 300,
            "y": 200,
            "w": 280,
            "h": 200,
            "fill": "#e7f5ff",
        },
        {
            "label": "AS 65002",
            "x": 640,
            "y": 60,
            "w": 200,
            "h": 340,
            "fill": "#ffe8e8",
        },
    ],
    "troubleshoot_bgp_route_filtering": [
        {
            "label": "Upstream ISP",
            "x": 300,
            "y": 40,
            "w": 240,
            "h": 140,
            "fill": "#ffe8e8",
        },
        {
            "label": "Enterprise edge + internal",
            "x": 120,
            "y": 220,
            "w": 600,
            "h": 360,
            "fill": "#e7f5ff",
        },
    ],
}


def _circular_positions(nodes: list[str]) -> dict[str, tuple[float, float]]:
    cx, cy = 450.0, 320.0
    r = 220.0
    n = len(nodes)
    out: dict[str, tuple[float, float]] = {}
    for i, name in enumerate(nodes):
        ang = 2 * math.pi * i / n - math.pi / 2
        out[name] = (cx + r * math.cos(ang), cy + r * math.sin(ang))
    return out


def _node_positions(task_id: str, node_names: list[str]) -> dict[str, tuple[float, float]]:
    if task_id in _PRESET_POSITIONS:
        preset = _PRESET_POSITIONS[task_id]
        missing = [n for n in node_names if n not in preset]
        if not missing:
            return {n: preset[n] for n in node_names}
    return _circular_positions(node_names)


def _rect(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    bg: str,
    stroke: str = "#1e1e1e",
) -> dict[str, Any]:
    eid = _eid()
    return {
        "type": "rectangle",
        "version": 1,
        "versionNonce": _nonce(),
        "isDeleted": False,
        "id": eid,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "angle": 0,
        "x": x,
        "y": y,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "width": w,
        "height": h,
        "seed": _nonce(),
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
        "index": None,
    }


def _text(
    x: float,
    y: float,
    text: str,
    *,
    font_size: int = 20,
    w: float = 200,
    h: float = 36,
) -> dict[str, Any]:
    return {
        "type": "text",
        "version": 1,
        "versionNonce": _nonce(),
        "isDeleted": False,
        "id": _eid(),
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "angle": 0,
        "x": x,
        "y": y,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "width": w,
        "height": h,
        "seed": _nonce(),
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "boundElements": None,
        "updated": 1,
        "link": None,
        "locked": False,
        "fontSize": font_size,
        "fontFamily": 1,
        "text": text,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": text,
        "lineHeight": 1.25,
        "autoResize": True,
        "index": None,
    }


def _arrow(x1: float, y1: float, x2: float, y2: float) -> dict[str, Any]:
    min_x = min(x1, x2)
    min_y = min(y1, y2)
    p1 = (x1 - min_x, y1 - min_y)
    p2 = (x2 - min_x, y2 - min_y)
    w = max(abs(p2[0] - p1[0]), 1)
    h = max(abs(p2[1] - p1[1]), 1)
    return {
        "type": "arrow",
        "version": 1,
        "versionNonce": _nonce(),
        "isDeleted": False,
        "id": _eid(),
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "angle": 0,
        "x": min_x,
        "y": min_y,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "width": w,
        "height": h,
        "seed": _nonce(),
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "boundElements": None,
        "updated": 1,
        "link": None,
        "locked": False,
        "startBinding": None,
        "endBinding": None,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "points": [list(p1), list(p2)],
        "elbowed": False,
        "index": None,
    }


BOX_W = 130.0
BOX_H = 64.0


def _center_rect(cx: float, cy: float) -> tuple[float, float]:
    return (cx - BOX_W / 2, cy - BOX_H / 2)


def _box_center(xy: tuple[float, float]) -> tuple[float, float]:
    x, y = xy
    return (x + BOX_W / 2, y + BOX_H / 2)


def build_scene(task_path: Path) -> dict[str, Any]:
    data = json.loads(task_path.read_text(encoding="utf-8"))
    task_id = data["task_id"]
    topo = data["topology"]
    nodes = [n["name"] for n in topo["nodes"]]
    links: list[tuple[str, str]] = []
    for link in topo["links"]:
        a, b = link["endpoints"]
        n1, n2 = a.split(":")[0], b.split(":")[0]
        links.append((n1, n2))

    positions = _node_positions(task_id, nodes)
    elements: list[dict[str, Any]] = []

    # Region backgrounds (behind routers)
    for region in _REGIONS.get(task_id, []):
        r = _rect(
            region["x"],
            region["y"],
            region["w"],
            region["h"],
            bg=region["fill"],
            stroke="#868e96",
        )
        r["opacity"] = 55
        r["strokeWidth"] = 1
        elements.append(r)
        elements.append(
            _text(
                region["x"] + 8,
                region["y"] + 8,
                region["label"],
                font_size=16,
                w=region["w"] - 16,
                h=28,
            )
        )

    title = f"{task_id}"
    elements.append(_text(40, 20, title, font_size=28, w=900, h=40))
    elements.append(
        _text(
            40,
            52,
            "Generated from benchmark task JSON (links = L3 adjacency). "
            "Adjust layout and styling in Excalidraw as needed.",
            font_size=14,
            w=900,
            h=24,
        )
    )

    node_elements: dict[str, dict[str, Any]] = {}
    for name in nodes:
        cx, cy = positions[name]
        rx, ry = _center_rect(cx, cy)
        rect = _rect(rx, ry, BOX_W, BOX_H, bg="#dee2e6")
        node_elements[name] = rect
        elements.append(rect)
        tw = min(BOX_W - 8, max(60, len(name) * 12))
        elements.append(
            _text(
                rx + (BOX_W - tw) / 2,
                ry + BOX_H / 2 - 12,
                name,
                font_size=18,
                w=tw,
                h=28,
            )
        )

    seen_edges: set[tuple[str, str]] = set()
    for n1, n2 in links:
        key = tuple(sorted((n1, n2)))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        c1 = _box_center(_center_rect(*positions[n1]))
        c2 = _box_center(_center_rect(*positions[n2]))
        elements.append(_arrow(c1[0], c1[1], c2[0], c2[1]))

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "gridSize": None,
            "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--tasks-dir",
        type=Path,
        default=None,
        help="Directory containing task JSON files (default: MDPI multi_turn/ or repo tasks/multi_turn)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=_default_excalidraw_output(),
        help="Output directory for .excalidraw files",
    )
    args = ap.parse_args()
    tasks_dir = args.tasks_dir if args.tasks_dir is not None else _default_tasks_dir()
    if not tasks_dir.is_dir():
        raise SystemExit(f"Tasks directory not found: {tasks_dir}")
    json_files = sorted(tasks_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(
            f"No *.json task files in {tasks_dir}. "
            "Pass --tasks-dir or add task JSON next to excalidraw/ under mdpi_decentralized_paper/multi_turn."
        )

    args.output.mkdir(parents=True, exist_ok=True)

    for path in json_files:
        scene = build_scene(path)
        out = args.output / f"{path.stem}.excalidraw"
        out.write_text(json.dumps(scene, indent=2), encoding="utf-8")
        print(f"Wrote {out}")

    print(f"Done. Open .excalidraw files in Excalidraw or Obsidian Excalidraw.")


if __name__ == "__main__":
    main()
