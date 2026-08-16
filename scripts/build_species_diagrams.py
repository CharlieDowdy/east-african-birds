#!/usr/bin/env python3
"""Build the diagram manifest and a review queue for every species.

The script deliberately does not copy illustrations from copyrighted field guides.
It creates deterministic prompts/metadata for original artwork and records which
species still need an illustration. Run from the repository root.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIES = ROOT / "data/species.json"
OUT = ROOT / "data/diagrams.json"
QUEUE = ROOT / "data/diagram_queue.json"

with SPECIES.open(encoding="utf-8") as f:
    data = json.load(f)

birds = data.get("species", [])
assets = {}
queue = []

for bird in birds:
    sid = bird["id"]
    assets[sid] = {
        "species_id": sid,
        "name": bird.get("name", ""),
        "scientific": bird.get("scientific", ""),
        "status": "planned",
        "asset": None,
        "views": ["side-profile"],
        "include_sex_difference": True,
        "include_juvenile": False,
        "include_flight_view": False,
        "include_id_labels": True,
        "prompt": (
            "Original scientific field-guide illustration of "
            f"{bird.get('name', '')} ({bird.get('scientific', '')}), "
            "accurate East African plumage and proportions, clean neutral "
            "background, side profile, natural posture, identification-focused, "
            "no text, no watermark, no copied field-guide artwork."
        ),
    }
    queue.append(sid)

manifest = {
    "version": 2,
    "description": "Per-species original illustration manifest for the digital field guide.",
    "art_style": "Original scientific field-guide plate with accurate plumage, proportions and identification markings.",
    "license_policy": "Only original artwork or assets with verified reuse rights may be added.",
    "assets": assets,
    "status": {
        "planned": len(queue),
        "ready": 0,
        "review": 0,
    },
}

OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
QUEUE.write_text(json.dumps({"version": 1, "species_ids": queue}, indent=2) + "\n", encoding="utf-8")
print(f"Prepared {len(birds)} species diagram records")
