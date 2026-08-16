import json
import time
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data" / "species.json"
PHOTOS_FILE = ROOT / "data" / "photos.json"

API = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = (
    "EastAfricanBirds/1.0 "
    "https://github.com/CharlieDowdy/east-african-birds"
)

MAX_PHOTOS = 2
REQUEST_DELAY = 0.5

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT,
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

        if (
            isinstance(data, dict)
            and "species" in data
        ):
            return data["species"]

        return data

    except Exception:

        return {}


def save_photos(data):

    payload = {
        "version": 4,
        "generated_by": (
            "scripts/build_photos.py"
        ),
        "provider": "Wikimedia Commons",
        "species": data,
    }

    PHOTOS_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def search_commons(scientific):

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": (
            f'"{scientific}" filetype:bitmap'
        ),
        "gsrnamespace": "6",
        "gsrlimit": "10",
        "prop": "imageinfo",
        "iiprop": (
            "url|size|mime|extmetadata"
        ),
        "iiurlwidth": "1000",
    }

    try:

        response = session.get(
            API,
            params=params,
            timeout=45,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:

        print(
            f"  Commons request failed: {error}"
        )

        return None


def get_metadata(info, key):

    metadata = info.get(
        "extmetadata",
        {}
    )

    item = metadata.get(key)

    if not item:
        return ""

    return (
        item.get("value")
        or ""
    )


def extract_photos(data, scientific):

    if not data:
        return []

    pages = data.get(
        "query",
        {}
    ).get(
        "pages",
        []
    )

    photos = []

    seen = set()

    for page in pages:

        info_list = page.get(
            "imageinfo",
            []
        )

        if not info_list:
            continue

        info = info_list[0]

        mime = (
            info.get("mime")
            or ""
        ).lower()

        if not mime.startswith("image/"):
            continue

        url = (
            info.get("thumburl")
            or info.get("url")
        )

        if not url:
            continue

        title = page.get(
            "title",
            ""
        )

        if title in seen:
            continue

        license_name = get_metadata(
            info,
            "LicenseShortName"
        )

        usage_terms = get_metadata(
            info,
            "UsageTerms"
        )

        artist = get_metadata(
            info,
            "Artist"
        )

        description = get_metadata(
            info,
            "ImageDescription"
        )

        file_page = (
            "https://commons.wikimedia.org/wiki/"
            + quote(
                title.replace(
                    " ",
                    "_"
                )
            )
        )

        photos.append({
            "title": title,
            "url": url,
            "source": file_page,
            "provider": "Wikimedia Commons",
            "license": (
                license_name
                or usage_terms
                or "See source"
            ),
            "artist": (
                artist
                or "Unknown"
            ),
            "description": description,
            "scientific_name": scientific,
        })

        seen.add(title)

        if len(photos) >= MAX_PHOTOS:
            break

    return photos


def main():

    birds = load_species()

    existing = load_existing()

    total = len(birds)

    with_two = 0
    with_one = 0
    with_zero = 0

    print()
    print(
        f"Building photo database for "
        f"{total} species..."
    )
    print()

    for number, bird in enumerate(
        birds,
        start=1
    ):

        bird_id = bird.get("id")

        name = bird.get(
            "name",
            "Unknown"
        )

        scientific = (
            bird.get("scientific")
            or ""
        ).strip()

        if not bird_id:
            continue

        old = existing.get(
            bird_id
        )

        # Only skip if we already have
        # the required 2 photos.
        if (
            isinstance(old, list)
            and len(old) >= MAX_PHOTOS
        ):

            print(
                f"[{number}/{total}] "
                f"{name} — already has 2 photos"
            )

            with_two += 1
            continue

        print(
            f"[{number}/{total}] "
            f"{name}"
        )

        print(
            f"  Scientific: {scientific}"
        )

        result = search_commons(
            scientific
        )

        photos = extract_photos(
            result,
            scientific
        )

        existing[bird_id] = photos

        if len(photos) >= 2:

            print(
                "  ✓ Found 2 photos"
            )

            with_two += 1

        elif len(photos) == 1:

            print(
                "  ⚠ Found 1 photo"
            )

            with_one += 1

        else:

            print(
                "  ✗ No suitable photos found"
            )

            with_zero += 1

        # Save continuously.
        save_photos(existing)

        time.sleep(
            REQUEST_DELAY
        )

        if number % 25 == 0:

            print()
            print(
                "Progress:"
            )

            print(
                f"  2+ photos: {with_two}"
            )

            print(
                f"  1 photo:   {with_one}"
            )

            print(
                f"  0 photos:  {with_zero}"
            )

            print()

    save_photos(existing)

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
        f"Species:       {total}"
    )

    print(
        f"2+ photos:     {with_two}"
    )

    print(
        f"1 photo:       {with_one}"
    )

    print(
        f"0 photos:      {with_zero}"
    )

    print()


if __name__ == "__main__":
    main()
