import json
import time
import random
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data" / "species.json"
PHOTOS_FILE = ROOT / "data" / "photos.json"

API = "https://api.inaturalist.org/v2/observations"

OPEN_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
}

MAX_PHOTOS = 5

# Keep requests slow enough to avoid hammering iNaturalist.
REQUEST_DELAY = 1.2

MAX_RETRIES = 6


session = requests.Session()

session.headers.update({
    "User-Agent": (
        "EastAfricanBirds/1.0 "
        "https://github.com/CharlieDowdy/east-african-birds"
    ),
    "Accept": "application/json",
})


def load_species():

    data = json.loads(
        SPECIES_FILE.read_text(
            encoding="utf-8"
        )
    )

    return data.get("species", [])


def load_existing():

    if not PHOTOS_FILE.exists():
        return {}

    try:

        data = json.loads(
            PHOTOS_FILE.read_text(
                encoding="utf-8"
            )
        )

        # Support both:
        #
        # {
        #   "species": {...}
        # }
        #
        # and the older:
        #
        # {
        #   "bird-id": [...]
        # }

        if (
            isinstance(data, dict)
            and isinstance(data.get("species"), dict)
        ):
            return data["species"]

        return data

    except Exception:

        return {}


def save_database(database):

    PHOTOS_FILE.write_text(
        json.dumps(
            database,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def request_photos(scientific_name):

    params = {
        "taxon_name": scientific_name,
        "iconic_taxa": "Aves",
        "quality_grade": "research",
        "per_page": 30,
        "order_by": "votes",
        "order": "desc",
        "photo_license": "cc0,cc-by,cc-by-sa",
        "photos": "true",
    }

    for attempt in range(MAX_RETRIES):

        try:

            response = session.get(
                API,
                params=params,
                timeout=45,
            )

            if response.status_code == 429:

                wait = min(
                    60,
                    (2 ** attempt) +
                    random.uniform(0.5, 2.0)
                )

                print(
                    f"  Rate limited. "
                    f"Waiting {wait:.1f}s..."
                )

                time.sleep(wait)

                continue

            response.raise_for_status()

            return response.json()

        except requests.RequestException as error:

            if attempt == MAX_RETRIES - 1:

                print(
                    f"  Request failed: {error}"
                )

                return None

            wait = min(
                60,
                (2 ** attempt) +
                random.uniform(0.5, 2.0)
            )

            print(
                f"  Request error. "
                f"Retrying in {wait:.1f}s..."
            )

            time.sleep(wait)

    return None


def extract_photos(data):

    photos = []

    seen = set()

    for observation in (
        data.get("results", [])
    ):

        for photo in (
            observation.get("photos", [])
        ):

            license_code = (
                photo.get("license_code")
                or ""
            ).lower()

            if license_code not in OPEN_LICENSES:
                continue

            photo_id = photo.get("id")

            if not photo_id:
                continue

            if photo_id in seen:
                continue

            url = (
                photo.get("url")
                or photo.get("original_url")
            )

            if not url:
                continue

            # Use the larger iNaturalist version.
            if "/medium." in url:

                url = url.replace(
                    "/medium.",
                    "/large."
                )

            photos.append({
                "id": photo_id,
                "url": url,
                "license": license_code,
                "attribution": (
                    photo.get("attribution")
                    or "Photographer not supplied"
                ),
                "observation_id": (
                    observation.get("id")
                ),
            })

            seen.add(photo_id)

            if len(photos) >= MAX_PHOTOS:

                return photos

    return photos


def get_photos(scientific_name):

    if not scientific_name:
        return []

    data = request_photos(
        scientific_name
    )

    if not data:
        return []

    return extract_photos(data)


def main():

    birds = load_species()

    existing = load_existing()

    total = len(birds)

    print()
    print(
        f"Building photo database for "
        f"{total} species..."
    )
    print()

    species_with_photos = 0

    total_photos = 0

    for number, bird in enumerate(
        birds,
        start=1
    ):

        bird_id = bird.get("id")

        name = bird.get(
            "name",
            "Unknown"
        )

        scientific = bird.get(
            "scientific"
        )

        if not bird_id:
            continue

        # IMPORTANT:
        #
        # Only skip a species if it ALREADY
        # has photos.
        #
        # Empty [] entries from the previous
        # broken run MUST be retried.

        old_photos = existing.get(
            bird_id
        )

        if (
            isinstance(old_photos, list)
            and len(old_photos) > 0
        ):

            print(
                f"[{number}/{total}] "
                f"{name} — already has "
                f"{len(old_photos)} photos"
            )

            species_with_photos += 1

            total_photos += len(
                old_photos
            )

            continue

        print(
            f"[{number}/{total}] "
            f"{name}"
        )

        print(
            f"  Scientific: "
            f"{scientific}"
        )

        photos = get_photos(
            scientific
        )

        existing[bird_id] = photos

        if photos:

            print(
                f"  ✓ Found "
                f"{len(photos)} photos"
            )

            species_with_photos += 1

            total_photos += len(
                photos
            )

        else:

            print(
                "  – No suitable "
                "licensed photos found"
            )

        # Save after every species.
        #
        # This means the workflow can safely
        # continue if it stops.

        save_database(existing)

        # Respect API rate limits.

        time.sleep(
            REQUEST_DELAY
        )

    save_database(existing)

    print()
    print(
        "================================"
    )
    print(
        "PHOTO DATABASE COMPLETE"
    )
    print(
        "================================"
    )

    print(
        f"Species processed: {total}"
    )

    print(
        f"Species with photos: "
        f"{species_with_photos}"
    )

    print(
        f"Total photos: "
        f"{total_photos}"
    )

    print(
        f"Species without photos: "
        f"{total - species_with_photos}"
    )

    print()


if __name__ == "__main__":

    main()
