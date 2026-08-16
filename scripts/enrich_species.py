import json
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]

SPECIES_FILE = ROOT / "data" / "species.json"
DETAILS_FILE = ROOT / "data" / "species_details.json"

GBIF = "https://api.gbif.org/v1/species"


# ============================================================
# COUNTRIES USED BY THE WEBSITE
# ============================================================

TARGET_COUNTRIES = {
    "KE": "Kenya",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "ET": "Ethiopia",
}


# GBIF can return either country codes or country names
# depending on the record. Normalise both.
COUNTRY_ALIASES = {
    "KE": "KE",
    "KENYA": "KE",

    "TZ": "TZ",
    "TANZANIA": "TZ",
    "UNITED REPUBLIC OF TANZANIA": "TZ",

    "UG": "UG",
    "UGANDA": "UG",

    "ET": "ET",
    "ETHIOPIA": "ET",
}


SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "EastAfricanBirds/1.0"
})


# ============================================================
# API REQUEST
# ============================================================

def get_json(url, params=None):

    for attempt in range(3):

        try:

            response = SESSION.get(
                url,
                params=params,
                timeout=30
            )

            if response.status_code == 429:

                wait = 5 * (attempt + 1)

                print(
                    f"  Rate limited. "
                    f"Waiting {wait}s..."
                )

                time.sleep(wait)

                continue


            if not response.ok:

                print(
                    f"  GBIF request failed: "
                    f"{response.status_code}"
                )

                return None


            return response.json()


        except requests.RequestException as exc:

            print(
                f"  Request error: {exc}"
            )

            if attempt < 2:
                time.sleep(3)

            else:
                return None


    return None


# ============================================================
# SPECIES MATCH
# ============================================================

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

        "matched_name":
            data.get("scientificName"),

        "canonical_name":
            data.get("canonicalName"),

        "match_type":
            data.get("matchType")

    }


# ============================================================
# PROFILE
# ============================================================

def get_profile(key):

    return get_json(
        f"{GBIF}/{key}/speciesProfiles"
    )


# ============================================================
# CONSERVATION STATUS
# ============================================================

def get_status(key):

    return get_json(
        f"{GBIF}/{key}/iucnRedListCategory"
    )


# ============================================================
# DISTRIBUTION
# ============================================================

def get_distribution(key):

    return get_json(
        f"{GBIF}/{key}/distributions"
    )


# ============================================================
# CLEAN PROFILE
# ============================================================

def clean_profile(data):

    if not data:
        return {}


    results = data.get(
        "results",
        []
    )


    if not results:
        return {}


    profile = results[0]

    output = {}


    if profile.get("habitat"):
        output["habitat"] = profile["habitat"]


    if profile.get("sizeInMillimeter"):
        output["size_mm"] = (
            profile["sizeInMillimeter"]
        )


    if profile.get("massInGram"):
        output["mass_g"] = (
            profile["massInGram"]
        )


    return output


# ============================================================
# CLEAN STATUS
# ============================================================

def clean_status(data):

    if not data:
        return None


    return (
        data.get("category")
        or
        data.get(
            "iucnRedListCategory"
        )
    )


# ============================================================
# FIND OUR FOUR COUNTRIES
# ============================================================

def clean_distribution(data):

    if not data:
        return {
            "distribution": [],
            "countries": []
        }


    results = data.get(
        "results",
        []
    )


    raw_distribution = []

    found_countries = set()


    for item in results:

        if not isinstance(item, dict):
            continue


        # Keep the original country/locality
        # information for reference.
        country = item.get("country")

        locality = item.get("locality")


        value = (
            country
            or locality
        )


        if value and value not in raw_distribution:

            raw_distribution.append(value)


        # ----------------------------------------------------
        # Country field
        # ----------------------------------------------------

        if country:

            country_text = (
                str(country)
                .strip()
                .upper()
            )


            if country_text in COUNTRY_ALIASES:

                found_countries.add(
                    COUNTRY_ALIASES[
                        country_text
                    ]
                )


        # ----------------------------------------------------
        # Some GBIF records may return the country
        # inside a locality-style value.
        # ----------------------------------------------------

        if locality:

            locality_text = (
                str(locality)
                .strip()
                .upper()
            )


            for alias, code in COUNTRY_ALIASES.items():

                if alias in locality_text:

                    found_countries.add(
                        code
                    )


    countries = [

        code

        for code in TARGET_COUNTRIES

        if code in found_countries

    ]


    return {

        "distribution":
            raw_distribution,

        "countries":
            countries

    }


# ============================================================
# SAVE DATABASE
# ============================================================

def save_database(details):

    output = {

        "version": 3,

        "generated_by":
            "scripts/enrich_species.py",

        "scope": [
            "KE",
            "TZ",
            "UG",
            "ET"
        ],

        "scope_names": [
            "Kenya",
            "Tanzania",
            "Uganda",
            "Ethiopia"
        ],

        "sources": [
            "GBIF Species API"
        ],

        "species":
            details

    }


    DETAILS_FILE.write_text(

        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"

    )


# ============================================================
# MAIN
# ============================================================

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


    birds = database.get(
        "species",
        []
    )


    if not birds:

        raise SystemExit(
            "No species found in species.json"
        )


    # --------------------------------------------------------
    # Load existing database
    # --------------------------------------------------------

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


    print()
    print("=" * 60)
    print("East African Birds - Country Enrichment")
    print("=" * 60)
    print()
    print(
        f"Total species: {len(birds)}"
    )
    print()
    print(
        "Website countries:"
    )
    print(
        "  🇰🇪 Kenya"
    )
    print(
        "  🇹🇿 Tanzania"
    )
    print(
        "  🇺🇬 Uganda"
    )
    print(
        "  🇪🇹 Ethiopia"
    )
    print()
    print("=" * 60)
    print()


    for number, bird in enumerate(
        birds,
        start=1
    ):

        species_id = bird["id"]

        scientific = bird.get(
            "scientific"
        )


        if not scientific:

            continue


        current = details.get(
            species_id,
            {}
        )


        print(
            f"[{number}/{len(birds)}] "
            f"{bird.get('name')}"
        )


        # ----------------------------------------------------
        # Use existing GBIF key where possible.
        #
        # This is important because it means the workflow
        # doesn't need to rematch all 1,851 birds.
        # ----------------------------------------------------

        key = current.get(
            "gbif_key"
        )


        if not key:

            print(
                f"  Matching: "
                f"{scientific}"
            )


            match = match_species(
                scientific
            )


            if not match:

                print(
                    "  ✗ Could not match species"
                )

                details[species_id] = {

                    **current,

                    "countries": [],

                    "sources": [

                        {

                            "provider":
                                "GBIF",

                            "matched":
                                False

                        }

                    ]

                }


                save_database(
                    details
                )

                time.sleep(0.2)

                continue


            key = match[
                "gbif_key"
            ]


            current = {

                **current,

                "gbif_key":
                    key,

                "matched_name":
                    match[
                        "matched_name"
                    ],

                "match_type":
                    match[
                        "match_type"
                    ]

            }


        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Always refresh distribution.
        #
        # This fixes the old database instead of skipping
        # already-enriched species.
        # ----------------------------------------------------

        print(
            "  Checking distribution..."
        )


        distribution_data = (
            get_distribution(key)
        )


        cleaned = clean_distribution(
            distribution_data
        )


        countries = cleaned[
            "countries"
        ]


        print(
            "  Countries: "
            +
            (
                ", ".join(
                    countries
                )
                if countries
                else "None found"
            )
        )


        # ----------------------------------------------------
        # Preserve existing information.
        # ----------------------------------------------------

        current[
            "distribution"
        ] = cleaned[
            "distribution"
        ]


        current[
            "countries"
        ] = countries


        # ----------------------------------------------------
        # Only fetch profile/status when missing.
        # ----------------------------------------------------

        if not current.get(
            "habitat"
        ):

            profile = clean_profile(
                get_profile(key)
            )

            current.update(
                profile
            )


        if (
            "conservation_status"
            not in current
        ):

            status = clean_status(
                get_status(key)
            )

            current[
                "conservation_status"
            ] = status


        current[
            "sources"
        ] = [

            {

                "provider":
                    "GBIF",

                "species_api":
                    f"{GBIF}/{key}"

            }

        ]


        details[
            species_id
        ] = current


        # ----------------------------------------------------
        # Save after EVERY bird.
        # ----------------------------------------------------

        save_database(
            details
        )


        # ----------------------------------------------------
        # API delay.
        # ----------------------------------------------------

        time.sleep(
            0.25
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    counts = {
        "KE": 0,
        "TZ": 0,
        "UG": 0,
        "ET": 0
    }


    for record in details.values():

        for code in record.get(
            "countries",
            []
        ):

            if code in counts:

                counts[code] += 1


    print()
    print("=" * 60)
    print("COUNTRY ENRICHMENT COMPLETE")
    print("=" * 60)
    print()
    print(
        f"🇰🇪 Kenya:      {counts['KE']}"
    )
    print(
        f"🇹🇿 Tanzania:   {counts['TZ']}"
    )
    print(
        f"🇺🇬 Uganda:     {counts['UG']}"
    )
    print(
        f"🇪🇹 Ethiopia:   {counts['ET']}"
    )
    print()
    print(
        "species_details.json updated."
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
