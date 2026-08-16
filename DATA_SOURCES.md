# Bird data sources and licensing

The app uses source-backed data. It must not present AI-generated natural-history text as verified fact.

## Source hierarchy

1. **African Bird Club (ABC) country checklists** — country occurrence/checklist data. ABC states that its checklists contain species recorded in the country and documented in scientific and peer-reviewed publications. The checklists are maintained from referenced works and validated with country recorders.
   - https://www.africanbirdclub.org/checklists/
   - https://www.birdpics.co.za/abcbirdlists/

2. **Avibase** — regional checklist, scientific names, taxonomic order and status flags. The project's starting species dataset is explicitly sourced from the Eastern Africa Avibase checklist.
   - https://avibase.bsc-eoc.org/checklist.jsp?region=AFE

3. **GBIF** — taxonomic backbone and occurrence records. GBIF provides APIs for species and occurrence data; individual publisher records retain their own licensing.
   - https://www.gbif.org/

4. **BirdLife International DataZone** — conservation assessments and species distribution-map reference. The app stores links/references rather than copying BirdLife's protected factsheet text or spatial datasets. BirdLife's terms prohibit scraping/reposting its data and require permission for commercial use.
   - https://datazone.birdlife.org/
   - https://datazone.birdlife.org/terms-and-conditions

5. **Wikimedia/Wikipedia** — optional natural-history source where a suitable species article exists. Only short source-derived fields may be imported, with attribution and the applicable CC BY-SA licence retained. This is a fallback source, not a substitute for ornithological references.

6. **Xeno-canto / Macaulay Library** — sound/media discovery and links. Audio files are not copied into the repository unless their individual licence explicitly permits redistribution.

## Editorial rule

A field is labelled `verified` only when it comes from an identified source. If no reliable source is available, the value is left empty and the UI says that the field is awaiting verification. The application never fills missing ornithological facts with generated guesses.

## Copyright

The project is inspired by the structure and usefulness of regional field guides, but it does not copy text, artwork, plates or maps from *Birds of East Africa* or other commercial field guides. Where a source has restrictive terms, the app links to that source instead of redistributing its protected content.
