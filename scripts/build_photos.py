import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data/species.json"
PHOTOS_FILE = ROOT / "data/photos.json"

API = "https://api.inaturalist.org/v2/observations"

session = requests.Session()
session.headers.update({
    "User-Agent": "EastAfricanBirds/1.0"
})

OPEN_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa"
}


def get_photos(scientific_name):

    params = {
        "taxon_name": scientific_name,
        "quality_grade": "research",
        "per_page": 10,
        "order_by": "votes",
        "order": "desc",
        "photo_license": "cc0,cc-by,cc-by-sa"
    }

    try:

        response = session.get(
            API,
            params=params,
            timeout=30
        )

        if response.status_code == 429:

            print("Rate limited. Waiting...")
            time.sleep(10)

            response = session.get(
                API,
                params=params,
                timeout=30
            )

        if not response.ok:

            print(
                "Request failed:",
                response.status_code
            )

            return []

        data = response.json()

    except requests.RequestException as error:

        print(
            "Request error:",
            error
        )

        return []


    photos = []

    for observation in data.get(
        "results",
        []
    ):

        for photo in observation.get(
            "photos",
            []
        ):

            license_code = (
                photo.get("license_code")
                or ""
            ).lower()

            if license_code not in OPEN_LICENSES:
                continue

            url = (
                photo.get("url")
                or photo.get("original_url")
            )

            if not url:
                continue

            # Prefer the large version.
            if "/medium." in url:

                url = url.replace(
                    "/medium.",
                    "/large."
                )

            record = {
                "id": photo.get("id"),
                "url": url,
                "license": license_code,
                "attribution":
                    photo.get(
                        "attribution",
                        "Photographer not supplied"
                    ),
                "observation_id":
                    observation.get("id")
            }

            if not any(
                x["id"] == record["id"]
                for x in photos
            ):

                photos.append(record)

            if len(photos) >= 5:
                return photos

    return photos


def main():

    database = json.loads(
        SPECIES_FILE.read_text(
            encoding="utf-8"
        )
    )

    birds = database.get(
        "species",
        []
    )

    existing = {}

    if PHOTOS_FILE.exists():

        try:

            existing = json.loads(
                PHOTOS_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            existing = {}


    print(
        f"Building photo database for "
        f"{len(birds)} species..."
    )


    for number, bird in enumerate(
        birds,
        start=1
    ):

        bird_id = bird["id"]

        if bird_id in existing:

            print(
                f"[{number}/{len(birds)}] "
                f"{bird['name']} - already done"
            )

            continue


        scientific = bird.get(
            "scientific"
        )

        if not scientific:

            existing[bird_id] = []
            continue


        print(
            f"[{number}/{len(birds)}] "
            f"{bird['name']}"
        )


        photos = get_photos(
            scientific
        )

        existing[bird_id] = photos


        # Save after every bird so the workflow
        # can safely continue if interrupted.

        PHOTOS_FILE.write_text(
            json.dumps(
                existing,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )


        time.sleep(0.25)


    print()
    print("PHOTO DATABASE COMPLETE")
    print(
        "Species processed:",
        len(existing)
    )

    with_photos = sum(
        1
        for photos in existing.values()
        if photos
    )

    total_photos = sum(
        len(photos)
        for photos in existing.values()
    )

    print(
        "Species with photos:",
        with_photos
    )

    print(
        "Total photos:",
        total_photos
    )


if __name__ == "__main__":
    main()
