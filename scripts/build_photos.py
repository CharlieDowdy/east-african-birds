import json
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data/species.json"
PHOTOS_FILE = ROOT / "data/photos.json"

API = "https://api.inaturalist.org/v2/observations"

OPEN_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
}

# iNaturalist annotation IDs
FEMALE = ("9", "10")
MALE = ("9", "11")
JUVENILE = ("1", "8")


session = requests.Session()

session.headers.update({
    "User-Agent": "EastAfricanBirds/1.0"
})


def request_observations(scientific_name, extra_params=None, per_page=50):
    params = {
        "taxon_name": scientific_name,
        "quality_grade": "research",
        "per_page": per_page,
        "order_by": "votes",
        "order": "desc",
        "photo_license": "cc0,cc-by,cc-by-sa",
        "has[]": "photos",
    }

    if extra_params:
        params.update(extra_params)

    for attempt in range(5):
        try:
            response = session.get(
                API,
                params=params,
                timeout=45,
            )

            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            if response.ok:
                return response.json().get("results", [])

            print(
                f"  iNaturalist returned HTTP "
                f"{response.status_code}"
            )

            return []

        except requests.RequestException as error:
            print(f"  Request error: {error}")

            if attempt < 4:
                time.sleep(5 * (attempt + 1))

    return []


def get_photo_url(photo):
    url = (
        photo.get("url")
        or photo.get("original_url")
    )

    if not url:
        return None

    if "/medium." in url:
        url = url.replace(
            "/medium.",
            "/large."
        )

    return url


def photo_record(photo, observation, category):
    license_code = (
        photo.get("license_code")
        or ""
    ).lower()

    if license_code not in OPEN_LICENSES:
        return None

    url = get_photo_url(photo)

    if not url:
        return None

    return {
        "id": photo.get("id"),
        "url": url,
        "license": license_code,
        "attribution": (
            photo.get("attribution")
            or "Photographer not supplied"
        ),
        "observation_id": observation.get("id"),
        "category": category,
        "source": "iNaturalist",
    }


def get_annotations(observation):
    """
    Return annotation pairs such as:
    ("9", "11") = male
    ("9", "10") = female
    ("1", "8") = juvenile
    """

    found = set()

    for annotation in observation.get(
        "annotations",
        []
    ):
        attribute = annotation.get(
            "controlled_attribute"
        ) or {}

        value = annotation.get(
            "controlled_value"
        ) or {}

        attribute_id = str(
            attribute.get("id", "")
        )

        value_id = str(
            value.get("id", "")
        )

        if attribute_id and value_id:
            found.add(
                (attribute_id, value_id)
            )

    return found


def add_unique(target, record):
    if not record:
        return

    record_id = record.get("id")

    if not record_id:
        return

    if any(
        x.get("id") == record_id
        for x in target
    ):
        return

    target.append(record)


def collect_species_photos(scientific_name):
    """
    First retrieve a large set of good licensed observations.

    We then use iNaturalist annotations to identify:
      - verified male
      - verified female
      - verified juvenile

    We never guess these categories from appearance.
    """

    result = {
        "male": [],
        "female": [],
        "juvenile": [],
        "general": [],
    }

    observations = request_observations(
        scientific_name,
        per_page=50,
    )

    # Categorise annotated observations.
    for observation in observations:

        annotations = get_annotations(
            observation
        )

        photos = observation.get(
            "photos",
            []
        )

        for photo in photos:

            license_code = (
                photo.get("license_code")
                or ""
            ).lower()

            if license_code not in OPEN_LICENSES:
                continue

            # Male
            if MALE in annotations:
                add_unique(
                    result["male"],
                    photo_record(
                        photo,
                        observation,
                        "male",
                    )
                )

            # Female
            if FEMALE in annotations:
                add_unique(
                    result["female"],
                    photo_record(
                        photo,
                        observation,
                        "female",
                    )
                )

            # Juvenile
            if JUVENILE in annotations:
                add_unique(
                    result["juvenile"],
                    photo_record(
                        photo,
                        observation,
                        "juvenile",
                    )
                )

            # General photo
            add_unique(
                result["general"],
                photo_record(
                    photo,
                    observation,
                    "general",
                )
            )

    # We only need a few general backup photos.
    result["general"] = result["general"][:6]

    # If a verified category is missing, make a targeted
    # request for that annotation.
    missing_queries = []

    if not result["male"]:
        missing_queries.append(
            (
                "male",
                {
                    "term_id": "9",
                    "term_value_id": "11",
                },
            )
        )

    if not result["female"]:
        missing_queries.append(
            (
                "female",
                {
                    "term_id": "9",
                    "term_value_id": "10",
                },
            )
        )

    if not result["juvenile"]:
        missing_queries.append(
            (
                "juvenile",
                {
                    "term_id": "1",
                    "term_value_id": "8",
                },
            )
        )

    for category, params in missing_queries:

        # Juvenile is optional, so don't spend excessive
        # requests trying to find one.
        if (
            category == "juvenile"
            and len(observations) >= 20
        ):
            continue

        targeted = request_observations(
            scientific_name,
            extra_params=params,
            per_page=10,
        )

        for observation in targeted:

            annotations = get_annotations(
                observation
            )

            # Make absolutely sure the returned observation
            # actually contains the requested annotation.
            if params["term_id"] == "9":
                wanted = (
                    params["term_id"],
                    params["term_value_id"],
                )
            else:
                wanted = (
                    params["term_id"],
                    params["term_value_id"],
                )

            if wanted not in annotations:
                continue

            for photo in observation.get(
                "photos",
                []
            ):

                add_unique(
                    result[category],
                    photo_record(
                        photo,
                        observation,
                        category,
                    )
                )

                if result[category]:
                    break

            if result[category]:
                break

    # Only keep one representative photo for each
    # sex/life-stage category.
    result["male"] = result["male"][:1]
    result["female"] = result["female"][:1]
    result["juvenile"] = result["juvenile"][:1]

    return result


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

    print(
        f"Building detailed photo database "
        f"for {len(birds)} species..."
    )

    # Start fresh so changing the photo pipeline
    # actually rebuilds the database.
    existing = {}

    for number, bird in enumerate(
        birds,
        start=1
    ):

        bird_id = bird["id"]

        scientific = bird.get(
            "scientific"
        )

        print()
        print(
            f"[{number}/{len(birds)}] "
            f"{bird.get('name', bird_id)}"
        )

        print(
            f"  Scientific: {scientific}"
        )

        if not scientific:
            existing[bird_id] = {
                "male": [],
                "female": [],
                "juvenile": [],
                "general": [],
            }
            continue

        photos = collect_species_photos(
            scientific
        )

        existing[bird_id] = photos

        print(
            f"  Male: {len(photos['male'])}"
        )

        print(
            f"  Female: {len(photos['female'])}"
        )

        print(
            f"  Juvenile: {len(photos['juvenile'])}"
        )

        print(
            f"  General: {len(photos['general'])}"
        )

        # Save after every bird.
        PHOTOS_FILE.write_text(
            json.dumps(
                existing,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        time.sleep(0.35)

    print()
    print("=" * 50)
    print("PHOTO DATABASE COMPLETE")
    print("=" * 50)

    species_with_male = sum(
        1
        for x in existing.values()
        if x.get("male")
    )

    species_with_female = sum(
        1
        for x in existing.values()
        if x.get("female")
    )

    species_with_juvenile = sum(
        1
        for x in existing.values()
        if x.get("juvenile")
    )

    total_photos = sum(
        len(x.get("male", []))
        + len(x.get("female", []))
        + len(x.get("juvenile", []))
        + len(x.get("general", []))
        for x in existing.values()
    )

    print(
        f"Species processed: {len(existing)}"
    )

    print(
        f"Species with verified male photo: "
        f"{species_with_male}"
    )

    print(
        f"Species with verified female photo: "
        f"{species_with_female}"
    )

    print(
        f"Species with verified juvenile photo: "
        f"{species_with_juvenile}"
    )

    print(
        f"Total stored photos: {total_photos}"
    )


if __name__ == "__main__":
    main()
