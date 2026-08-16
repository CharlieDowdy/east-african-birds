import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data" / "species.json"
PHOTOS_FILE = ROOT / "data" / "photos.json"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
INAT_API = "https://api.inaturalist.org/v2/observations"

OPEN_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
}

# ============================================================
# TEST MODE
#
# Keep this at 5 for the first run.
#
# After confirming the first 5 birds work, change:
#
#     TEST_LIMIT = 5
#
# to:
#
#     TEST_LIMIT = None
#
# ============================================================

TEST_LIMIT = 5


session = requests.Session()

session.headers.update({
    "User-Agent":
        "EastAfricanBirds/1.0 "
        "(https://github.com/CharlieDowdy/east-african-birds)"
})


# ============================================================
# BASIC HELPERS
# ============================================================

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

        # New format
        if isinstance(data, dict):
            if "species" in data:
                return data["species"]

            return data

    except Exception:
        pass

    return {}


def save_database(database):

    payload = {
        "version": 5,
        "generated_by":
            "scripts/build_photos.py",
        "providers": [
            "Wikimedia Commons",
            "iNaturalist"
        ],
        "species": database
    }

    PHOTOS_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def clean_text(value):

    if not value:
        return ""

    value = re.sub(
        r"<[^>]+>",
        "",
        str(value)
    )

    value = value.replace(
        "&nbsp;",
        " "
    )

    value = value.replace(
        "&amp;",
        "&"
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def clean_artist(value):

    return clean_text(value)


# ============================================================
# WIKIMEDIA COMMONS
# ============================================================

def commons_search(scientific_name):

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",

        "gsrsearch":
            f'"{scientific_name}"',

        "gsrnamespace": "6",
        "gsrlimit": "30",

        "prop": "imageinfo",

        "iiprop":
            "url|mime|size|extmetadata",

        "iiurlwidth": "1200"
    }

    for attempt in range(5):

        try:

            response = session.get(
                COMMONS_API,
                params=params,
                timeout=45
            )

            if response.status_code == 429:

                wait = 5 * (attempt + 1)

                print(
                    f"  Commons rate limited. "
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            return response.json()

        except Exception as error:

            print(
                f"  Commons error: {error}"
            )

            if attempt < 4:
                time.sleep(
                    3 * (attempt + 1)
                )

    return {}


def is_probably_real_photo(info):

    metadata = (
        info.get("extmetadata")
        or {}
    )

    description = clean_text(
        metadata.get(
            "ImageDescription",
            {}
        ).get("value", "")
    ).lower()

    title = clean_text(
        info.get(
            "title",
            ""
        )
    ).lower()

    combined = (
        title + " " + description
    )

    # Avoid obvious illustrations,
    # paintings, drawings, maps, etc.
    bad_words = [
        "illustration",
        "illustrated",
        "drawing",
        "painting",
        "watercolor",
        "watercolour",
        "engraving",
        "lithograph",
        "sketch",
        "diagram",
        "map",
        "statue",
        "sculpture",
        "model"
    ]

    return not any(
        word in combined
        for word in bad_words
    )


def commons_photos(scientific_name):

    data = commons_search(
        scientific_name
    )

    pages = (
        data.get("query", {})
        .get("pages", [])
    )

    photos = []

    seen = set()

    for page in pages:

        title = page.get(
            "title",
            ""
        )

        if title in seen:
            continue

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

        if not mime.startswith(
            "image/"
        ):
            continue

        if not is_probably_real_photo(
            info
        ):
            continue

        metadata = (
            info.get("extmetadata")
            or {}
        )

        license_name = clean_text(
            metadata.get(
                "LicenseShortName",
                {}
            ).get("value", "")
        )

        # We only keep licences we can
        # safely expose in the app.
        license_lower = (
            license_name.lower()
        )

        if not any(
            x in license_lower
            for x in [
                "cc0",
                "cc by",
                "cc-by",
                "public domain"
            ]
        ):
            continue

        url = (
            info.get("thumburl")
            or info.get("url")
        )

        if not url:
            continue

        artist = clean_artist(
            metadata.get(
                "Artist",
                {}
            ).get("value", "")
        )

        source = (
            "https://commons.wikimedia.org/wiki/"
            + quote(
                title.replace(
                    " ",
                    "_"
                )
            )
        )

        photos.append({
            "id":
                "commons-" + str(
                    page.get("pageid")
                ),

            "url": url,

            "source": source,

            "provider":
                "Wikimedia Commons",

            "license":
                license_name
                or "See source",

            "artist":
                artist
                or "Unknown",

            "category":
                "general"
        })

        seen.add(title)

        if len(photos) >= 8:
            break

    return photos


# ============================================================
# INATURALIST
# ============================================================

def inat_observations(
    scientific_name,
    term_id=None,
    term_value_id=None
):

    params = {
        "taxon_name":
            scientific_name,

        "quality_grade":
            "research",

        "per_page":
            50,

        "order_by":
            "votes",

        "order":
            "desc",

        # IMPORTANT:
        # This is the correct API filter.
        "photo_license":
            "cc0,cc-by,cc-by-sa",

        "has[]":
            "photos"
    }

    if term_id is not None:
        params["term_id"] = str(
            term_id
        )

    if term_value_id is not None:
        params["term_value_id"] = str(
            term_value_id
        )

    for attempt in range(6):

        try:

            response = session.get(
                INAT_API,
                params=params,
                timeout=45
            )

            if response.status_code == 429:

                wait = 10 * (
                    attempt + 1
                )

                print(
                    f"  iNaturalist rate limited. "
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            data = response.json()

            return data.get(
                "results",
                []
            )

        except Exception as error:

            print(
                f"  iNaturalist error: "
                f"{error}"
            )

            if attempt < 5:
                time.sleep(
                    5 * (attempt + 1)
                )

    return []


def make_inat_photo(
    photo,
    observation,
    category
):

    license_code = (
        photo.get(
            "license_code"
        )
        or ""
    ).lower()

    if license_code not in OPEN_LICENSES:
        return None

    url = (
        photo.get("url")
        or photo.get(
            "original_url"
        )
    )

    if not url:
        return None

    # iNaturalist documents replacing
    # the size component to get another
    # available size.
    url = url.replace(
        "/medium.",
        "/large."
    )

    return {
        "id":
            "inat-" + str(
                photo.get("id")
            ),

        "url":
            url,

        "source":
            (
                "https://www.inaturalist.org/"
                "observations/"
                + str(
                    observation.get(
                        "id"
                    )
                )
            ),

        "provider":
            "iNaturalist",

        "license":
            license_code,

        "artist":
            photo.get(
                "attribution"
            )
            or "Unknown",

        "observation_id":
            observation.get(
                "id"
            ),

        "category":
            category
    }


def first_annotated_photo(
    observations,
    category
):

    for observation in observations:

        for photo in observation.get(
            "photos",
            []
        ):

            result = make_inat_photo(
                photo,
                observation,
                category
            )

            if result:
                return result

    return None


# ============================================================
# BUILD ONE SPECIES
# ============================================================

def build_species_photos(
    scientific_name
):

    result = {
        "male": [],
        "female": [],
        "juvenile": [],
        "general": []
    }

    # --------------------------------------------------------
    # 1. GENERAL PHOTOS
    # --------------------------------------------------------

    print(
        "  Searching Wikimedia Commons..."
    )

    general = commons_photos(
        scientific_name
    )

    result["general"] = general[:8]

    print(
        f"  Commons general photos: "
        f"{len(result['general'])}"
    )

    # --------------------------------------------------------
    # 2. MALE
    # Sex = group 9, Male = value 11
    # --------------------------------------------------------

    print(
        "  Searching verified male photos..."
    )

    male_obs = inat_observations(
        scientific_name,
        term_id=9,
        term_value_id=11
    )

    male = first_annotated_photo(
        male_obs,
        "male"
    )

    if male:
        result["male"].append(male)

    # --------------------------------------------------------
    # 3. FEMALE
    # Sex = group 9, Female = value 10
    # --------------------------------------------------------

    print(
        "  Searching verified female photos..."
    )

    female_obs = inat_observations(
        scientific_name,
        term_id=9,
        term_value_id=10
    )

    female = first_annotated_photo(
        female_obs,
        "female"
    )

    if female:
        result["female"].append(
            female
        )

    # --------------------------------------------------------
    # 4. JUVENILE
    # Life Stage = group 1,
    # Juvenile = value 8
    # --------------------------------------------------------

    print(
        "  Searching verified juvenile photos..."
    )

    juvenile_obs = inat_observations(
        scientific_name,
        term_id=1,
        term_value_id=8
    )

    juvenile = first_annotated_photo(
        juvenile_obs,
        "juvenile"
    )

    if juvenile:
        result["juvenile"].append(
            juvenile
        )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    birds = load_species()

    existing = load_existing()

    limit = TEST_LIMIT

    if limit is None:
        selected = birds
    else:
        selected = birds[:limit]

    print()
    print(
        "=========================================="
    )
    print(
        "East African Birds Photo Builder"
    )
    print(
        "=========================================="
    )

    print(
        f"Total species in database: "
        f"{len(birds)}"
    )

    print(
        f"Species being processed: "
        f"{len(selected)}"
    )

    print()

    for number, bird in enumerate(
        selected,
        start=1
    ):

        bird_id = bird.get(
            "id"
        )

        name = bird.get(
            "name",
            bird_id
        )

        scientific = (
            bird.get(
                "scientific"
            )
            or ""
        ).strip()

        print()
        print(
            f"[{number}/{len(selected)}] "
            f"{name}"
        )

        print(
            f"  Scientific: {scientific}"
        )

        if not scientific:
            continue

        result = build_species_photos(
            scientific
        )

        existing[bird_id] = result

        print()
        print(
            f"  ✓ Male: "
            f"{len(result['male'])}"
        )

        print(
            f"  ✓ Female: "
            f"{len(result['female'])}"
        )

        print(
            f"  ✓ Juvenile: "
            f"{len(result['juvenile'])}"
        )

        print(
            f"  ✓ General: "
            f"{len(result['general'])}"
        )

        # Save immediately.
        save_database(
            existing
        )

        # Small pause between species.
        time.sleep(1)

    print()
    print(
        "=========================================="
    )
    print(
        "TEST COMPLETE"
    )
    print(
        "=========================================="
    )

    print(
        "The database has been saved."
    )

    if TEST_LIMIT is not None:

        print()
        print(
            "IMPORTANT:"
        )

        print(
            "This was a 5-species test."
        )

        print(
            "Check photos.json before "
            "running all 1,851 species."
        )


if __name__ == "__main__":
    main()
