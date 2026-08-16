import json
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
# PROCESS ALL 1,851 SPECIES
# ============================================================

TEST_LIMIT = None


session = requests.Session()

session.headers.update({
    "User-Agent":
        "EastAfricanBirds/1.0 "
        "(https://github.com/CharlieDowdy/east-african-birds)"
})


# ============================================================
# FILES
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

        if isinstance(data, dict):

            if "species" in data:
                return data["species"]

            return data

    except Exception:
        pass

    return {}


def save_database(database):

    payload = {
        "version": 6,
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


# ============================================================
# TEXT HELPERS
# ============================================================

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


# ============================================================
# WIKIMEDIA COMMONS
# ============================================================

def commons_search(query):

    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "30",
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
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


def commons_is_photo(info):

    mime = (
        info.get("mime")
        or ""
    ).lower()

    if not mime.startswith("image/"):
        return False

    metadata = (
        info.get("extmetadata")
        or {}
    )

    title = clean_text(
        info.get("title", "")
    ).lower()

    description = clean_text(
        metadata.get(
            "ImageDescription",
            {}
        ).get("value", "")
    ).lower()

    text = title + " " + description

    bad = [
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
        "sculpture"
    ]

    return not any(
        word in text
        for word in bad
    )


def commons_license(info):

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

    lower = license_name.lower()

    if "cc0" in lower:
        return "CC0"

    if "cc by-sa" in lower:
        return "CC BY-SA"

    if "cc-by-sa" in lower:
        return "CC BY-SA"

    if "cc by" in lower:
        return "CC BY"

    if "cc-by" in lower:
        return "CC BY"

    if "public domain" in lower:
        return "Public Domain"

    return None


def commons_get_photos(
    scientific_name,
    category="general",
    limit=3
):

    query = (
        f'"{scientific_name}"'
    )

    if category == "male":
        query += " male"

    elif category == "female":
        query += " female"

    elif category == "juvenile":
        query += " juvenile"

    data = commons_search(query)

    pages = (
        data.get("query", {})
        .get("pages", [])
    )

    results = []

    seen = set()

    for page in pages:

        page_id = page.get(
            "pageid"
        )

        if page_id in seen:
            continue

        info_list = page.get(
            "imageinfo",
            []
        )

        if not info_list:
            continue

        info = info_list[0]

        if not commons_is_photo(info):
            continue

        license_name = commons_license(
            info
        )

        if not license_name:
            continue

        url = (
            info.get("thumburl")
            or info.get("url")
        )

        if not url:
            continue

        metadata = (
            info.get("extmetadata")
            or {}
        )

        artist = clean_text(
            metadata.get(
                "Artist",
                {}
            ).get("value", "")
        )

        title = page.get(
            "title",
            ""
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

        results.append({
            "id":
                f"commons-{page_id}",

            "url":
                url,

            "source":
                source,

            "provider":
                "Wikimedia Commons",

            "license":
                license_name,

            "artist":
                artist or "Unknown",

            "category":
                category
        })

        seen.add(page_id)

        if len(results) >= limit:
            break

    return results


# ============================================================
# iNATURALIST
# ============================================================

def inat_search(
    scientific_name,
    sex=None,
    juvenile=False
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

        "photo_license":
            "cc0,cc-by,cc-by-sa",

        "has[]":
            "photos"
    }

    # Sex:
    # 9 = Sex
    # 10 = Female
    # 11 = Male

    if sex == "male":

        params["term_id"] = "9"
        params["term_value_id"] = "11"

    elif sex == "female":

        params["term_id"] = "9"
        params["term_value_id"] = "10"

    # Life stage:
    # 1 = Life Stage
    # 8 = Juvenile

    elif juvenile:

        params["term_id"] = "1"
        params["term_value_id"] = "8"

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
                    observation.get("id")
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


def first_inat_photo(
    observations,
    category
):

    for observation in observations:

        photos = observation.get(
            "photos",
            []
        )

        for photo in photos:

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

def build_species(
    scientific_name
):

    result = {
        "male": [],
        "female": [],
        "juvenile": [],
        "general": []
    }

    # --------------------------------------------------------
    # MALE
    # --------------------------------------------------------

    print(
        "  Searching verified male..."
    )

    male_obs = inat_search(
        scientific_name,
        sex="male"
    )

    male = first_inat_photo(
        male_obs,
        "male"
    )

    if male:

        result["male"].append(
            male
        )

    else:

        male_commons = commons_get_photos(
            scientific_name,
            category="male",
            limit=1
        )

        result["male"] = male_commons

    # --------------------------------------------------------
    # FEMALE
    # --------------------------------------------------------

    print(
        "  Searching verified female..."
    )

    female_obs = inat_search(
        scientific_name,
        sex="female"
    )

    female = first_inat_photo(
        female_obs,
        "female"
    )

    if female:

        result["female"].append(
            female
        )

    else:

        female_commons = commons_get_photos(
            scientific_name,
            category="female",
            limit=1
        )

        result["female"] = female_commons

    # --------------------------------------------------------
    # JUVENILE
    # --------------------------------------------------------

    print(
        "  Searching verified juvenile..."
    )

    juvenile_obs = inat_search(
        scientific_name,
        juvenile=True
    )

    juvenile = first_inat_photo(
        juvenile_obs,
        "juvenile"
    )

    if juvenile:

        result["juvenile"].append(
            juvenile
        )

    else:

        juvenile_commons = commons_get_photos(
            scientific_name,
            category="juvenile",
            limit=1
        )

        result["juvenile"] = (
            juvenile_commons
        )

    # --------------------------------------------------------
    # THREE ADDITIONAL PHOTOS
    # --------------------------------------------------------

    print(
        "  Searching 3 additional photos..."
    )

    result["general"] = (
        commons_get_photos(
            scientific_name,
            category="general",
            limit=3
        )
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    birds = load_species()

    existing = load_existing()

    if TEST_LIMIT is None:

        selected = birds

    else:

        selected = birds[:TEST_LIMIT]

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

        result = build_species(
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
            f"  ✓ Additional: "
            f"{len(result['general'])}"
        )

        # Save after every species.
        save_database(
            existing
        )

        time.sleep(1)

    print()
    print(
        "=========================================="
    )
    print(
        "PHOTO DATABASE COMPLETE"
    )
    print(
        "=========================================="
    )

    print(
        f"Processed: {len(selected)} species"
    )

    print(
        "The photo database has been saved."
    )


if __name__ == "__main__":
    main()
