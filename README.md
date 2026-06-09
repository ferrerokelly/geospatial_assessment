# Colorado School Board Districts: Technical Assessment

**Kelly Ferrero \| Part 1: Design & Planning**

------------------------------------------------------------------------

## Contents

| File                            | Description                                                                                                                                            |
|-------------------------|-----------------------------------------------|
| `design_document.md`            | Full written design document: data model, source strategy, geometry acquisition approach, quality assessment, and tradeoffs                            |
| `explore_sources.py`            | Python script: downloads DOLA shapefile, explores attributes, runs structured quality validation, demonstrates attribute join, produces a district map |
| `README.md`                     | This file                                                                                                                                              |
| `colorado_school_districts.png` | Map of all 178 districts colored by geographic size                                                                                                    |

------------------------------------------------------------------------

## How to Run

### Requirements

``` bash
pip install geopandas pandas matplotlib requests shapely
```

### Run

``` bash
python explore_sources.py
```

**What it does:**

1\. Downloads the DOLA Colorado school district shapefile (\~2MB) on first run, skips if already cached

2\. Normalizes column names and loads with geopandas; Prints initial exploration: fields, CRS, sample records, geometry source metadata

3\. Runs structured quality validation: row count, invalid geometries, nulls, duplicate IDs, bounding box, area sanity

4\. Explores attributes: null rates, websites, renamed districts

5\. Demonstrates an attribute join: calculates district area in km², classifies districts by size

6\. Produces `colorado_school_districts.png` map of all 178 districts colored by geographic size

**Expected runtime:** \~15 seconds including download on first run.

------------------------------------------------------------------------

## Notes

-   No data files are committed: `explore_sources.py` downloads everything programmatically
-   Part 1 is design and exploration. Part 2 will include a full acquisition pipeline
