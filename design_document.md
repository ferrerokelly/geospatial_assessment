# Colorado School Board Districts Design Document

**Kelly Ferrero \| Technical Assessment \| Part 1: Design & Planning**

------------------------------------------------------------------------

## 1. Data Model & Schema

### How would you structure this geospatial dataset?

The core unit is a school district, either a single polygon or multipolygon for non-contiguous districts. The schema needs to support joins with voter files, election results, and other civic datasets, so stable IDs and clean string fields matter as much as the geometry itself.

### What fields matter beyond the geometry?

Proposed schema:

| Field                 | Type     | Source                     | Description                                                                                                     |
|-----------------|-----------------|-----------------|-----------------------|
| `district_id`         | string   | DOLA: `LG_ID`              | Unique state-assigned district identifier                                                                       |
| `district_name`       | string   | DOLA: `NAME`               | Official district name                                                                                          |
| `district_abbrev`     | string   | DOLA: `ABBREV_NAM`         | Abbreviated name                                                                                                |
| `previous_name`       | string   | DOLA: `PREV_NAME`          | Prior name if district was renamed (important for historical joins)                                             |
| `district_type`       | string   | Derived from NCES          | Unified / Elementary / Secondary                                                                                |
| `grade_range_low`     | string   | NCES: `LOGRADE`            | Lowest grade served (e.g. PK)                                                                                   |
| `grade_range_high`    | string   | NCES: `HIGRADE`            | Highest grade served (e.g. 12)                                                                                  |
| `seat_count`          | integer  | Ballotpedia/elections data | Number of board member seats (5, 6, or 7 per CO state law): not in GIS sources, derivable from election records |
| `mail_address`        | string   | DOLA: `MAIL_ADDRE`         | Mailing address                                                                                                 |
| `mail_city`           | string   | DOLA: `MAIL_CITY`          | City                                                                                                            |
| `mail_zip`            | string   | DOLA: `MAIL_ZIP`           | ZIP code                                                                                                        |
| `website`             | string   | DOLA: `WEBSITE_UR`         | District website                                                                                                |
| `geometry_source`     | string   | Derived                    | Where geometry came from (e.g. "DOLA, May 2025")                                                                |
| `geometry_source_url` | string   | Derived                    | Direct URL to source dataset                                                                                    |
| `acquired_date`       | date     | Derived                    | Date this record was pulled                                                                                     |
| `geometry`            | geometry | DOLA shapefile             | Polygon or MultiPolygon in WGS84 (EPSG:4326)                                                                    |

### How would you handle sub-districts for individual board member seats?

**Decision: Model board seats as a separate table linked to the parent district by `district_id`.**

This keeps the one-to-many relationship clean and can remain empty until data becomes available.

**Practical reality for Colorado:** Sub-district seat boundaries were not found in any public GIS source during this investigation. Colorado Secretary of State election records or direct outreach to the Colorado Department of Education or individual districts would be the most likely path to populating this table.

------------------------------------------------------------------------

## 2. Source Strategy

### Source 1: Colorado GIS Hub: DOLA (Primary)

**URL:** <https://geodata.colorado.gov/datasets/8771964233e043aa9835e008297a61a2_0>\
**Direct download:** <https://storage.googleapis.com/co-publicdata/dlschool.zip>\
**Maintainer:** Colorado Department of Local Affairs\
**Data last updated:** May 1, 2025

Colorado's official state GIS hub, maintained by the Department of Local Affairs. I downloaded the shapefile and inspected it directly. Key findings: 178 records matching the expected district count, rich Colorado-specific attributes including `LG_ID`, `NAME`, `PREV_NAME`, `WEBSITE_UR`, `MAIL_ADDRE`, 0 null values across all fields, 0 invalid geometries, and CRS already in EPSG:4326.

**Relationship to Census TIGER:** The `source` field in each record reads `Census TIGER SHP 2023` and `lastupdate` field shows `August 2024`. Colorado state officials submit boundary updates to Census via the School District Review Program (SDRP).

**Why DOLA is meaningfully different from using raw Census TIGER files directly:** The concerns listed in the instructions about Census TIGER are that coverage is incomplete and boundaries lag real-world changes. For Colorado, DOLA addresses the coverage concern as all 178 districts are included with complete attributes and no gaps. DOLA also carries Colorado-specific attributes that do not exist in TIGER: Colorado's own district identifier (`LG_ID`), mailing addresses, websites, and previous district names.

**Where the Census TIGER concerns still apply to DOLA:** The SDRP cycle introduces lag. Any district that changed its boundary after August 2024 would not be reflected in this dataset. Sub-district seat structures are absent entirely (this gap applies to DOLA, TIGER, and every other public source found).

**Decision: Primary Source**

------------------------------------------------------------------------

### Source 2: NCES EDGE: Composite School District Boundaries (Validation Reference)

**URL:** <https://nces.ed.gov/programs/edge/Geographic/DistrictBoundaries>\
**Maintainer:** National Center for Education Statistics

The NCES EDGE program publishes a composite boundary file combining Elementary, Secondary, and Unified district layers into a single national file, updated via SDRP. Like DOLA, it ultimately distributes state-submitted boundaries via Census.

**Where NCES adds value over DOLA:** It includes a district type field (`SDTYP`) distinguishing Unified, Elementary, and Secondary districts, which DOLA lacks, and grade range fields (`LOGRADE`, `HIGRADE`).

**Decision: Validation Reference (cross-reference district count, type, and grade range)**

------------------------------------------------------------------------

### Source 3: Colorado Department of Education: PDF Reference Maps (Reference only)

**URL:** <https://www.cde.state.co.us/sites/default/files/map-district.pdf>\
**Maintainer:** Colorado Department of Education

CDE publishes a statewide school district map as a PDF, created from "various print and GIS sources" and explicitly labeled "for general reference use only and should not be considered a precise representation of geographic or political borders."

It is useful for two purposes: visually verifying that DOLA boundaries look correct for a given region, and as a construction fallback for digitizing a specific district that is missing from all other sources. CDE also publishes an official district list in Excel with district names and numbers, which is useful as a completeness checklist.

**Decision: Reference only**

------------------------------------------------------------------------

### Source 4: Census Cartographic Boundary File (Ruled Out)

**URL:** <https://catalog.data.gov/dataset/2025-cartographic-boundary-file-shp-unified-school-district-for-colorado-1-500000>

Designed for small-scale thematic mapping. Boundaries are generalized for visual display rather than precise civic data use. Ruled out in favor of DOLA which is Colorado's own state-maintained source.

**Decision: Ruled Out**

------------------------------------------------------------------------

### Source 5: County GIS Portals (Not a statewide source)

I checked portals for Colorado's two largest counties, Denver and El Paso. El Paso County publishes some school district boundary data on their open data hub. Denver's geospatialDENVER portal has an education category but no standalone school district boundary dataset was found. DOLA already aggregates this data at the state level.

**Decision: Not suitable as a statewide source**

------------------------------------------------------------------------

## 3. Geometry Acquisition & Construction Approach

### Case 1: GIS Portal with Direct Download

Download programmatically using `requests`, extract the zip, load with `geopandas`, normalize column names on ingestion, validate CRS, and run quality checks before using. See `explore_sources.py`.

### Case 2: PDF Map with Described Boundaries

The CDE statewide PDF map is an example of this case. My approach would be to georeference the PDF by aligning it to known geographic control points: county corners, major highway intersections, or city centers using QGIS or a similar tool. Once georeferenced, district boundaries can be digitized manually by tracing outlines as vector polygons over the image. The resulting geometries must be validated against known anchors like county lines and major roads, and flagged explicitly as approximate with `geometry_source` set to something like `"CDE PDF map (approximate, reference-only source)"`.

This approach is practical for a small number of missing or suspected-stale districts, not for all 178 at once. It is the right fallback when a specific district is absent from DOLA.

### Case 3: Legal Descriptions in Text

Some districts define their boundaries through legal text referencing section lines, township/range coordinates, named roads, etc. My approach would be to parse the text to extract geographic references, then construct geometry by connecting the reference points. An LLM can accelerate the parsing step, but the output must be treated as untrusted and validated against a base map before use. Any geometry constructed this way should be flagged as `geometry_source: "constructed from legal description"`.

### Case 4: Nothing Available

When a district has no usable source of any kind, I would use the county boundary as a rough geographic proxy and flag it clearly as approximate, record the district with all available non-spatial attributes and a null or proxy geometry rather than fabricating one, and document the gap explicitly. A known-missing district is better than silently absent data. In practice, a phone call to CDE or the district itself could surface data that does not exist online.

------------------------------------------------------------------------

## 4. Quality Assessment

### What checks would you run?

**Automated checks** run on every dataset load and cover: row count against the expected 178 for Colorado; CRS verification; invalid geometry detection with explanations for any found; null checks on required fields (`lg_id`, `name`); duplicate ID detection; bounding box verification against Colorado's geographic extent; geometry type distribution; and area sanity checks using Colorado State Plane projection for accurate measurement, flagging districts smaller than 1 km² or larger than 15,000 km². See `explore_sources.py`.

**What would make me nervous even if it technically loaded:**

-   Geometries with implausible area (smaller than 1 km² or larger than 15,000 km² for Colorado)
-   Boundaries that don't follow county lines where they should. Most Colorado districts align with county boundaries; large deviations suggest stale or incorrect geometry
-   Gaps between adjacent districts. Blank space between neighboring districts suggests missing records
-   Overlapping polygons between non-enclave districts (districts should not overlap)
-   A MultiPolygon in an unexpected location. 8 MultiPolygons exist in DOLA, which is plausible for non-contiguous rural districts. A MultiPolygon in a dense urban area would warrant investigation
-   Stale geometry dates: the `lastupdate` field shows August 2024. Any district that changed its boundary since then would pass all automated checks but be wrong in reality. No code catches this, so it requires external knowledge or monitoring
-   District count changes between pipeline runs. If a run shows 177 or 179 where 178 are expected, something changed and it needs investigation before the update is accepted

**Visual inspection** catches what automated checks miss. Plotting all 178 districts colored by size allows spot-checking for stray polygons, missing regions, and shapes that don't match the known geography of Colorado, particularly the dense cluster of small districts in the Denver metro area. The output plot is produced by `explore_sources.py`.

------------------------------------------------------------------------

## 5. Tradeoffs & Open Questions

### What assumptions are you making?

DOLA's geometry reflects August 2024 boundaries and is current enough for this exercise. `LG_ID` is a stable join key that persists across DOLA updates (this would need verification before relying on it in production). 178 is the correct expected district count and any significant deviation is a data quality signal. All Colorado districts are Unified type per NCES. Sub-district seat boundaries are out of scope; the schema supports them but they are not collected here.

### Where does my plan break down?

**Geographic boundary changes** represent a limitation. The SDRP update cycle means boundary changes may lag by months. There is no automated way to detect whether a specific district changed its boundary since August 2024. It would require direct outreach or monitoring CDE announcements.

**Sub-district seat boundaries** are an unsolved gap. Board seat geometries for Colorado are not available in DOLA, NCES, county portals, or CDE's public data.

**Visual validation at scale** is not feasible in this timeframe. A boundary that is technically valid but subtly wrong will pass all automated checks and only be caught through manual review or external knowledge.

### What would you do differently with more time or resources?

Contact CDE directly to ask whether they maintain internal GIS data more current than what DOLA publishes, and whether board seat boundary data exists in any form. Download and run the full NCES EDGE cross-reference to compare district counts, name matching, and type classification against DOLA. Cross-reference against CDE's official district list (available as Excel) to validate that every district CDE recognizes has a corresponding geometry. Spot-check a sample of district boundaries against satellite imagery, focusing on districts with recent administrative changes. Build automated monitoring to detect when DOLA refreshes its dataset.

### Open Questions

-   Does CDE maintain internal GIS data more current than what DOLA publishes?
-   Are board seat sub-district boundaries available from any Colorado source?
-   What is DOLA's update cycle and how closely does it follow SDRP boundary submissions?
-   How are districts that span multiple counties handled in the DOLA geometry?

------------------------------------------------------------------------

## AI Usage Note

**Where AI assistance was used:** I used Claude to help structure the design document and draft code in `explore_sources.py`.

**How AI-generated suggestions were verified or modified:** All source investigation was done independently. I found and evaluated each source myself, downloaded the DOLA shapefile, and inspected the actual attribute data. All code was reviewed and tested locally.

**Parts written fully independently:** Source evaluation and reasoning for all sources, the finding that DOLA geometry traces to state-submitted boundaries via SDRP, the quality assessment and tradeoffs and open questions sections.

------------------------------------------------------------------------

*Kelly Ferrero \| Submitted for Murmuration Technical Assessment*
