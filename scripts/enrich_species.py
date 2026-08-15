import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data" / "species.json"
DETAILS_FILE = ROOT / "data" / "species_details.json"

GBIF = "https://api.gbif.org/v1/species"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "EastAfricanBirds/1.0"
})


def get_json(url, params=None):
    try:
        response = SESSION.get(
            url,
            params=params,
            timeout=30
        )

        if response.status_code == 429:
            time.sleep(5)
            response = SESSION.get(
                url,
                params=params,
                timeout=30
            )

        if not response.ok:
            print(
                f"GBIF request failed: "
                f"{response.status_code} {url}"
            )
            return None

        return response.json()

    except requests.RequestException as exc:
        print(f"Request error: {exc}")
        return None


def match_species(scientific_name):
    data = get_json(
        f"{GBIF}/match",
        {
            "name": scientific_name
        }
    )

    if not data:
        return None

    key = data.get("usageKey")

    if not key:
        return None

    return {
        "gbif_key": key,
        "matched_name": data.get("scientificName"),
        "canonical_name": data.get("canonicalName"),
        "match_type": data.get("matchType")
    }


def get_profile(key):
    return get_json(
        f"{GBIF}/{key}/speciesProfiles"
    )


def get_status(key):
    return get_json(
        f"{GBIF}/{key}/iucnRedListCategory"
    )


def get_distribution(key):
    return get_json(
        f"{GBIF}/{key}/distributions"
    )


def clean_profile(data):
    if not data:
        return {}

    results = data.get("results", [])

    if not results:
        return {}

    profile = results[0]

    output = {}

    if profile.get("habitat"):
        output["habitat"] = profile["habitat"]

    if profile.get("sizeInMillimeter"):
        output["size_mm"] = profile["sizeInMillimeter"]

    if profile.get("massInGram"):
        output["mass_g"] = profile["massInGram"]

    return output


def clean_status(data):
    if not data:
        return None

    return (
        data.get("category")
        or data.get("iucnRedListCategory")
    )


def clean_distribution(data):
    if not data:
        return []

    results = data.get("results", [])

    countries = []

    for item in results:

        country = (
            item.get("country")
            or item.get("locality")
        )

        if country and country not in countries:
            countries.append(country)

    return countries


def main():

    if not SPECIES_FILE.exists():
        raise SystemExit(
            "data/species.json was not found"
        )

    database = json.loads(
        SPECIES_FILE.read_text(
            encoding="utf-8"
        )
    )

    birds = database.get("species", [])

    if not birds:
        raise SystemExit(
            "No species found in species.json"
        )

    if DETAILS_FILE.exists():

        existing = json.loads(
            DETAILS_FILE.read_text(
                encoding="utf-8"
            )
        )

        details = existing.get(
            "species",
            {}
        )

    else:
        details = {}

    print(
        f"Enriching {len(birds)} species..."
    )

    for number, bird in enumerate(
        birds,
        start=1
    ):

        species_id = bird["id"]
        scientific = bird.get("scientific")

        if not scientific:
            continue

        # Don't repeatedly fetch records
        # that have already been matched.
        current = details.get(
            species_id,
            {}
        )

        if current.get("gbif_key"):
            print(
                f"[{number}/{len(birds)}] "
                f"{bird.get('name')} "
                f"- already enriched"
            )
            continue

        print(
            f"[{number}/{len(birds)}] "
            f"{bird.get('name')} "
            f"({scientific})"
        )

        match = match_species(scientific)

        if not match:
            details[species_id] = {
                "sources": [
                    {
                        "provider": "GBIF",
                        "matched": False
                    }
                ]
            }

            continue

        key = match["gbif_key"]

        profile = clean_profile(
            get_profile(key)
        )

        status = clean_status(
            get_status(key)
        )

        distribution = clean_distribution(
            get_distribution(key)
        )

        record = {
            **profile,

            "gbif_key": key,

            "matched_name":
                match["matched_name"],

            "match_type":
                match["match_type"],

            "conservation_status":
                status,

            "distribution":
                distribution,

            "sources": [
                {
                    "provider": "GBIF",
                    "species_api":
                        f"https://api.gbif.org/v1/species/{key}"
                }
            ]
        }

        details[species_id] = record

        # Save continuously so a temporary
        # failure doesn't lose everything.
        output = {
            "version": 2,
            "generated_by":
                "scripts/enrich_species.py",
            "sources": [
                "GBIF Species API"
            ],
            "species": details
        }

        DETAILS_FILE.write_text(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        # Be polite to the API.
        time.sleep(0.15)

    print(
        f"Finished. "
        f"Records written: {len(details)}"
    )


if __name__ == "__main__":
    main()
