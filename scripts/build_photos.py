import json
import re
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
SPECIES_FILE = ROOT / "data" / "species.json"
PHOTOS_FILE = ROOT / "data" / "photos.json"

INAT_API = "https://api.inaturalist.org/v2"
OPEN_LICENSES = {"cc0", "cc-by", "cc-by-sa"}

TEST_LIMIT = None

session = requests.Session()
session.headers.update({
    "User-Agent": "EastAfricanBirds/1.0 (https://github.com/CharlieDowdy/east-african-birds)"
})


def load_species():
    data = json.loads(SPECIES_FILE.read_text(encoding="utf-8"))
    return data.get("species", [])


def load_existing():
    if not PHOTOS_FILE.exists():
        return {}
    try:
        data = json.loads(PHOTOS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("species", data)
    except Exception:
        pass
    return {}


def save_database(database):
    payload = {
        "version": 7,
        "generated_by": "scripts/build_photos.py",
        "providers": ["iNaturalist"],
        "matching": "exact iNaturalist taxon ID; no descendant taxa accepted",
        "species": database,
    }
    PHOTOS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", "", str(value))
    value = value.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", value).strip()


def get_json(path, params, attempts=5):
    for attempt in range(attempts):
        try:
            response = session.get(
                f"{INAT_API}{path}",
                params=params,
                timeout=45,
            )
            if response.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  iNaturalist rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as error:
            print(f"  iNaturalist error: {error}")
            if attempt < attempts - 1:
                time.sleep(3 * (attempt + 1))
    return {}


def resolve_exact_taxon(scientific_name):
    """Return the iNaturalist species taxon ID only for an exact name match."""
    data = get_json(
        "/taxa",
        {
            "q": scientific_name,
            "rank": "species",
            "is_active": "true",
            "per_page": 20,
        },
    )
    wanted = scientific_name.strip().casefold()
    for taxon in data.get("results", []):
        if clean_text(taxon.get("name", "")).casefold() == wanted:
            return taxon.get("id")
    return None


def inat_search_exact(taxon_id, sex=None, juvenile=False):
    """Search iNaturalist, then reject every observation whose taxon is not exact."""
    params = {
        "taxon_id": taxon_id,
        "quality_grade": "research",
        "per_page": 50,
        "order_by": "votes",
        "order": "desc",
        "photo_license": "cc0,cc-by,cc-by-sa",
        "has[]": "photos",
    }

    if sex == "male":
        params["term_id"] = "9"
        params["term_value_id"] = "11"
    elif sex == "female":
        params["term_id"] = "9"
        params["term_value_id"] = "10"
    elif juvenile:
        params["term_id"] = "1"
        params["term_value_id"] = "8"

    data = get_json("/observations", params, attempts=6)
    observations = []

    for observation in data.get("results", []):
        observation_taxon = observation.get("taxon") or {}
        if observation_taxon.get("id") == taxon_id:
            observations.append(observation)

    return observations


def make_inat_photo(photo, observation, category, scientific_name, taxon_id):
    license_code = (photo.get("license_code") or "").lower()
    if license_code not in OPEN_LICENSES:
        return None

    url = photo.get("url") or photo.get("original_url")
    if not url:
        return None
    url = url.replace("/medium.", "/large.")

    return {
        "id": "inat-" + str(photo.get("id")),
        "url": url,
        "source": f"https://www.inaturalist.org/observations/{observation.get('id')}",
        "provider": "iNaturalist",
        "license": license_code,
        "artist": photo.get("attribution") or "Unknown",
        "observation_id": observation.get("id"),
        "taxon_id": taxon_id,
        "scientific_name": scientific_name,
        "category": category,
    }


def first_photo(observations, category, scientific_name, taxon_id):
    for observation in observations:
        # A second defensive check prevents accidental descendant/ancestor use.
        if (observation.get("taxon") or {}).get("id") != taxon_id:
            continue
        for photo in observation.get("photos", []):
            result = make_inat_photo(
                photo, observation, category, scientific_name, taxon_id
            )
            if result:
                return result
    return None


def build_species(scientific_name):
    taxon_id = resolve_exact_taxon(scientific_name)
    empty = {"male": [], "female": [], "juvenile": [], "general": []}

    if not taxon_id:
        print("  ! No exact iNaturalist species taxon found; leaving photos empty.")
        return empty

    print(f"  Exact iNaturalist taxon: {taxon_id}")
    result = empty

    male = first_photo(
        inat_search_exact(taxon_id, sex="male"),
        "male", scientific_name, taxon_id,
    )
    if male:
        result["male"].append(male)

    female = first_photo(
        inat_search_exact(taxon_id, sex="female"),
        "female", scientific_name, taxon_id,
    )
    if female:
        result["female"].append(female)

    juvenile = first_photo(
        inat_search_exact(taxon_id, juvenile=True),
        "juvenile", scientific_name, taxon_id,
    )
    if juvenile:
        result["juvenile"].append(juvenile)

    # General images are also restricted to the exact species taxon.
    general_obs = inat_search_exact(taxon_id)
    for observation in general_obs:
        if (observation.get("taxon") or {}).get("id") != taxon_id:
            continue
        for photo in observation.get("photos", []):
            image = make_inat_photo(
                photo, observation, "general", scientific_name, taxon_id
            )
            if image and image["id"] not in {p["id"] for p in result["general"]}:
                result["general"].append(image)
                if len(result["general"]) >= 3:
                    break
        if len(result["general"]) >= 3:
            break

    return result


def main():
    birds = load_species()
    database = load_existing()
    selected = birds if TEST_LIMIT is None else birds[:TEST_LIMIT]

    print("==========================================")
    print("East African Birds Exact Photo Builder")
    print("==========================================")
    print(f"Total species in database: {len(birds)}")
    print(f"Species being processed: {len(selected)}")

    for number, bird in enumerate(selected, start=1):
        bird_id = bird.get("id")
        name = bird.get("name", bird_id)
        scientific = (bird.get("scientific") or "").strip()

        print(f"\n[{number}/{len(selected)}] {name}")
        print(f"  Scientific: {scientific}")

        if not scientific:
            database[bird_id] = {"male": [], "female": [], "juvenile": [], "general": []}
            continue

        database[bird_id] = build_species(scientific)

        result = database[bird_id]
        print(f"  ✓ Male: {len(result['male'])}")
        print(f"  ✓ Female: {len(result['female'])}")
        print(f"  ✓ Juvenile: {len(result['juvenile'])}")
        print(f"  ✓ General: {len(result['general'])}")

    save_database(database)
    print("\nPhoto database saved.")


if __name__ == "__main__":
    main()
