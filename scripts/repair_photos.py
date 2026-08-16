#!/usr/bin/env python3
"""Replace unreliable bird photos with exact-taxonomy, openly licensed iNaturalist photos.

The old pipeline searched by text alone. This pipeline first resolves the scientific
name to an iNaturalist species taxon, then requests only research-grade observations
whose current taxon ID exactly matches that species. If no licensed exact match exists,
that species gets no replacement rather than an unverified photograph.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SPECIES_FILE = ROOT / "data/species.json"
PHOTOS_FILE = ROOT / "data/photos.json"
REPORT_FILE = ROOT / "data/photo_repair_report.json"

TAXA_API = "https://api.inaturalist.org/v1/taxa"
OBS_API = "https://api.inaturalist.org/v2/observations"
OPEN_LICENSES = {"cc0", "cc-by", "cc-by-sa"}

session = requests.Session()
session.headers.update({
    "User-Agent": "EastAfricanBirds/1.0 (https://github.com/CharlieDowdy/east-african-birds)"
})


def get_json(url: str, params: dict) -> dict:
    for attempt in range(5):
        try:
            r = session.get(url, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 4:
                return {}
            time.sleep(3 * (attempt + 1))
    return {}


def norm(value: str) -> str:
    return " ".join((value or "").lower().replace("×", "x").split())


def resolve_exact_taxon(scientific: str) -> dict | None:
    data = get_json(TAXA_API, {
        "q": scientific,
        "rank": "species",
        "per_page": 20,
        "order_by": "observations_count",
        "order": "desc",
    })
    target = norm(scientific)
    for taxon in data.get("results", []):
        names = {
            norm(taxon.get("name")),
            norm(taxon.get("preferred_common_name")),
        }
        if norm(taxon.get("name")) == target and taxon.get("rank") == "species":
            return taxon
    return None


def exact_observation_photo(taxon_id: int) -> dict | None:
    data = get_json(OBS_API, {
        "taxon_id": taxon_id,
        "quality_grade": "research",
        "per_page": 50,
        "order_by": "votes",
        "order": "desc",
        "photo_license": "cc0,cc-by,cc-by-sa",
        "has[]": "photos",
    })
    for obs in data.get("results", []):
        obs_taxon = obs.get("taxon") or {}
        if obs_taxon.get("id") != taxon_id:
            continue
        for photo in obs.get("photos", []):
            license_code = (photo.get("license_code") or "").lower()
            if license_code not in OPEN_LICENSES:
                continue
            url = photo.get("url") or photo.get("original_url")
            if not url:
                continue
            url = url.replace("/medium.", "/large.")
            return {
                "id": f"inat-{photo.get('id')}",
                "url": url,
                "source": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "provider": "iNaturalist",
                "license": license_code,
                "artist": photo.get("attribution") or "Unknown",
                "observation_id": obs.get("id"),
                "taxon_id": taxon_id,
                "taxon_scientific_name": obs_taxon.get("name"),
                "match": "exact_iNaturalist_taxon",
            }
    return None


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def main() -> None:
    species_data = load_json(SPECIES_FILE, {})
    birds = species_data.get("species", [])
    old = load_json(PHOTOS_FILE, {})
    old = old.get("species", old) if isinstance(old, dict) else {}

    repaired = {}
    report = {
        "version": 1,
        "provider": "iNaturalist",
        "policy": "Replace existing media only with research-grade media attached to the exact iNaturalist species taxon and an open licence (CC0, CC BY or CC BY-SA). No exact match means no replacement.",
        "species_total": len(birds),
        "replaced": 0,
        "no_verified_replacement": 0,
        "errors": 0,
        "species": {},
    }

    for number, bird in enumerate(birds, 1):
        sid = bird.get("id")
        scientific = (bird.get("scientific") or "").strip()
        if not sid or not scientific:
            continue
        print(f"[{number}/{len(birds)}] {bird.get('name')} — {scientific}")
        taxon = resolve_exact_taxon(scientific)
        if not taxon:
            report["no_verified_replacement"] += 1
            report["species"][sid] = {"status": "no_exact_taxon"}
            repaired[sid] = {"male": [], "female": [], "juvenile": [], "general": []}
            continue
        photo = exact_observation_photo(taxon["id"])
        if photo:
            repaired[sid] = {"male": [], "female": [], "juvenile": [], "general": [photo]}
            report["replaced"] += 1
            report["species"][sid] = {
                "status": "replaced",
                "taxon_id": taxon["id"],
                "scientific": taxon.get("name"),
                "source": photo["source"],
                "license": photo["license"],
                "artist": photo["artist"],
            }
        else:
            # Do not retain a potentially incorrect image just because it exists.
            repaired[sid] = {"male": [], "female": [], "juvenile": [], "general": []}
            report["no_verified_replacement"] += 1
            report["species"][sid] = {
                "status": "no_open_exact_photo",
                "taxon_id": taxon["id"],
                "scientific": taxon.get("name"),
                "previous_media_removed": bool(old.get(sid)),
            }
        time.sleep(0.35)

    PHOTOS_FILE.write_text(
        json.dumps({
            "version": 7,
            "generated_by": "scripts/repair_photos.py",
            "providers": ["iNaturalist"],
            "verification": "Exact iNaturalist species taxon + research-grade observation + open licence",
            "species": repaired,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Replaced: {report['replaced']}")
    print(f"No verified replacement: {report['no_verified_replacement']}")


if __name__ == "__main__":
    main()
