# East African Birds — Data policy

## Goal
This project is a digital field guide for Kenya, Tanzania, Uganda, Rwanda and Burundi. Bird facts must be traceable to an identifiable source. AI may help with code, search and editorial organisation, but AI-generated natural-history claims are **not** treated as source data.

## Primary sources

### Taxonomy — AviList v2025b
AviList v2025b is the taxonomy backbone. AviList describes its checklist as a consensus taxonomy with taxonomic and nomenclatural components and makes the XLSX available under CC BY 4.0.

- URL: https://www.avilist.org/checklist/v2025b/
- Citation: AviList Core Team. 2026. AviList: The Global Avian Checklist, v2025b. https://doi.org/10.2173/avilist.v2025b
- Licence: CC BY 4.0

### Country occurrence/context — African Bird Club
African Bird Club country accounts are used as an authoritative research index for the five target countries. They provide country species information, endemic/near-endemic groupings, habitats, birding sites and references to national checklists.

- Kenya: https://www.africanbirdclub.org/countries/kenya/kenya-introduction/
- Tanzania: https://www.africanbirdclub.org/countries/tanzania/tanzania-introduction/
- Uganda: https://www.africanbirdclub.org/countries/uganda/uganda-introduction/
- Rwanda: https://www.africanbirdclub.org/countries/rwanda/rwanda-introduction/
- Burundi: https://www.africanbirdclub.org/countries/burundi/burundi-introduction/
- Country index: https://www.africanbirdclub.org/countries/

ABC should be treated as a source/index and cited, not copied wholesale into the app.

### Occurrence/taxonomic lookup — GBIF
GBIF is used for machine-readable taxonomic matching and occurrence evidence. The project records the source and retrieval date rather than treating occurrence records as prose natural-history descriptions.

- Species API documentation: https://techdocs.gbif.org/en/openapi/v1/species
- Species matching: https://www.gbif.org/tool/35eY57p7P4ifcF5RF6SKRZ/species-matching

### Identification, maps, photos and sounds — eBird / Birds of the World / Macaulay Library
These are research destinations and media sources. The app should store links and attribution where permitted by the relevant licence/API terms. Do not copy copyrighted account text into the repository.

- eBird species profiles: https://ebird.org/explore
- Birds of the World: https://birdsoftheworld.org/
- Macaulay Library: https://macaulaylibrary.org/

## Publishing rules

1. Taxonomic fields can be imported from AviList under its CC BY 4.0 licence with attribution.
2. Country presence should be represented as a sourced occurrence claim, with country/source/date metadata.
3. Conservation status must retain a source and assessment/version/date.
4. Natural-history prose must be either (a) written by a human from cited sources, (b) supplied under a licence that permits republication, or (c) stored only as a link/reference and not copied.
5. Photos and sounds require individual licence/attribution checks. A URL alone does not grant republication rights.
6. If a fact cannot be verified, the field remains empty or is labelled `not_verified`.
7. Never present an AI-generated guess as a field-guide fact.

## Current limitation
The repository's existing species/details files contain useful GBIF-derived information, but they do not by themselves constitute a complete, source-verified natural-history account for every East African species. The enrichment pipeline therefore produces provenance and research links first; human/source verification is required before publishing prose.
