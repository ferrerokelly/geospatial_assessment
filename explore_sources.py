"""
explore_sources.py
------------------
Source investigation and quality validation for Colorado school board district boundaries.
Technical Assessment — Part 1 | Kelly Ferrero

This script:
  1. Downloads the DOLA Colorado school district shapefile programmatically
  2. Explores fields, CRS, geometry validity, and district attributes
  3. Runs structured quality validation checks
  4. Demonstrates an attribute join (area calculation + size classification)
  5. Produces a map of all 178 Colorado districts colored by geographic size

Usage:
    pip install geopandas pandas matplotlib requests shapely
    python explore_sources.py

Data is downloaded on first run (~2MB). Subsequent runs skip the download.
"""

import os
import io
import zipfile
import logging
import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.validation import explain_validity

# ── SETUP ─────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# ── STEP 1: DOWNLOAD DOLA SHAPEFILE ──────────────────────────────────────────
# Source: Colorado GIS Hub, maintained by Dept. of Local Affairs

DOLA_URL = "https://storage.googleapis.com/co-publicdata/dlschool.zip"
dola_dir = os.path.join(DATA_DIR, "dola")
dola_shp = os.path.join(dola_dir, "dlschool.shp")

if not os.path.exists(dola_shp):
    logging.info(f"Downloading DOLA shapefile from {DOLA_URL}")
    r = requests.get(DOLA_URL, timeout=60)
    r.raise_for_status()
    os.makedirs(dola_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(dola_dir)
    logging.info(f"Extracted to: {dola_dir}")
else:
    logging.info(f"Using cached DOLA shapefile at {dola_shp}")


# ── STEP 2: LOAD AND EXPLORE ──────────────────────────────────────────────────

logging.info("Loading DOLA shapefile")
gdf = gpd.read_file(dola_shp)

# Normalize column names on ingestion — strip whitespace, lowercase, underscores
gdf.columns = gdf.columns.str.strip().str.lower().str.replace(" ", "_")

print("\n" + "="*60)
print("DOLA — Colorado School Districts: Initial Exploration")
print("="*60)
print(f"Shape:    {gdf.shape[0]} rows x {gdf.shape[1]} columns")
print(f"CRS:      {gdf.crs}")
print(f"Columns:  {gdf.columns.tolist()}")

key_cols = ["lg_id", "name", "source", "lastupdate", "website_ur"]
print(f"\nFirst 5 rows (key fields):")
print(gdf[key_cols].head(5).to_string(index=False))

# Geometry source: important finding about DOLA's relationship to Census TIGER
print(f"\n--- Geometry Source (source field) ---")
print(gdf["source"].value_counts().to_string())


print(f"\n--- Last Update Field ---")
print(gdf["lastupdate"].value_counts().to_string())


# ── STEP 3: QUALITY VALIDATION ────────────────────────────────────────────────

print("\n" + "="*60)
print("Quality Validation")
print("="*60)


def validate_districts(gdf: gpd.GeoDataFrame, source_name: str) -> dict:
    """
    Run structured quality checks on a school district GeoDataFrame.

    Checks performed:
      - Row count vs expected 178 for Colorado
      - CRS
      - Invalid geometries (with explanation for any found)
      - Null values in required fields (lg_id, name)
      - Duplicate district IDs
      - Bounding box within Colorado bounds
      - Geometry type distribution
      - Area sanity: min/max/mean in km2, flag suspiciously small/large

    Args:
        gdf: GeoDataFrame of school districts
        source_name: Label for logging output

    Returns:
        dict of validation findings
    """
    results = {"source": source_name, "row_count": len(gdf), "passed": True}
    print(f"\nValidating: {source_name}")

    # 1. Row count 
    count_ok = len(gdf) == 178
    results["count_ok"] = count_ok
    print(f"  Row count: {len(gdf)} {'✓' if count_ok else '✗ UNEXPECTED — expected 178'}")

    # 2. CRS
    results["crs"] = str(gdf.crs)
    print(f"  CRS: {gdf.crs}")

    # 3. Invalid geometries
    invalid_mask = ~gdf.is_valid
    invalid_count = int(invalid_mask.sum())
    results["invalid_geom_count"] = invalid_count
    if invalid_count > 0:
        print(f"  ✗ Invalid geometries: {invalid_count}")
        for idx, row in gdf[invalid_mask].iterrows():
            print(f"    → {row.get('name', idx)}: {explain_validity(row.geometry)}")
        results["passed"] = False
    else:
        print(f"  Invalid geometries: 0 ✓")

    # 4. Null check on required fields
    for col in ["lg_id", "name"]:
        if col in gdf.columns:
            nulls = int(gdf[col].isnull().sum())
            results[f"nulls_{col}"] = nulls
            if nulls > 0:
                print(f"  ✗ Nulls in '{col}': {nulls}")
                results["passed"] = False
            else:
                print(f"  Nulls in '{col}': 0 ✓")
        else:
            print(f"  ⚠ Column '{col}' not found")

    # 5. Duplicate IDs 
    if "lg_id" in gdf.columns:
        dupes = int(gdf["lg_id"].duplicated().sum())
        results["duplicate_ids"] = dupes
        if dupes > 0:
            print(f"  ✗ Duplicate lg_ids: {dupes}")
            results["passed"] = False
        else:
            print(f"  Duplicate IDs: 0 ✓")

    # 6. Bounding box 
    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
    results["bounding_box"] = [round(b, 4) for b in bounds]
    co_ok = (bounds[0] > -110 and bounds[2] < -101 and
             bounds[1] > 36  and bounds[3] < 42)
    results["within_co_bounds"] = bool(co_ok)
    print(f"  Bounding box: {results['bounding_box']}")
    print(f"  Within Colorado bounds: {'✓' if co_ok else '✗ OUT OF RANGE'}")
    if not co_ok:
        results["passed"] = False

    # 7. Geometry type distribution
    geom_types = gdf.geometry.geom_type.value_counts()
    results["geom_types"] = geom_types.to_dict()
    print(f"  Geometry types: {dict(geom_types)}")
    # Note: MultiPolygons are expected for non-contiguous districts

    # 8. Area sanity 
    gdf_proj = gdf.to_crs(epsg=26913)
    areas_km2 = gdf_proj.geometry.area / 1e6
    results["area_min_km2"]  = round(float(areas_km2.min()), 2)
    results["area_max_km2"]  = round(float(areas_km2.max()), 2)
    results["area_mean_km2"] = round(float(areas_km2.mean()), 2)
    print(f"  Area range: {results['area_min_km2']} – {results['area_max_km2']} km²"
          f" (mean {results['area_mean_km2']} km²)")

    # Flag suspiciously small districts (< 1 km² almost certainly an error)
    tiny = gdf[areas_km2 < 1]
    results["suspiciously_small"] = list(tiny["name"]) if "name" in gdf.columns else []
    if len(tiny) > 0:
        print(f"  ⚠ Suspiciously small (< 1 km²): {results['suspiciously_small']}")

    # Flag suspiciously large districts (> 15,000 km²)
    huge = gdf[areas_km2 > 15000]
    results["suspiciously_large"] = list(huge["name"]) if "name" in gdf.columns else []
    if len(huge) > 0:
        print(f"  ⚠ Suspiciously large (> 15,000 km²): {results['suspiciously_large']}")

    status = "PASSED" if results["passed"] else "FAILED"
    print(f"\n  Validation result: {status}")
    return results


validation_results = validate_districts(gdf, "DOLA Colorado School Districts")


# ── STEP 4: ATTRIBUTE EXPLORATION ────────────────────────────────────────────

print("\n" + "="*60)
print("Attribute Exploration")
print("="*60)

# Full null rate across all fields
print("Null counts by field:")
print(gdf.isnull().sum().to_string())

# Districts with websites
has_website = gdf["website_ur"].notna() & (gdf["website_ur"].str.strip() != "")
print(f"\nDistricts with websites: {has_website.sum()} / {len(gdf)}")

# Districts with previous names
has_prev = gdf["prev_name"].notna() & (gdf["prev_name"].str.strip() != "") & (gdf["prev_name"] != "NA")
print(f"Districts with previous names (renamed): {has_prev.sum()}")
if has_prev.sum() > 0:
    print("\nRenamed districts:")
    print(gdf[has_prev][["name", "prev_name"]].to_string(index=False))


# ── STEP 5: ATTRIBUTE JOIN DEMONSTRATION ─────────────────────────────────────
# Demonstrates attribute integration 
# Note: in production this pattern would join to an external table
# (e.g. election results, enrollment data) on lg_id.
# Here we demonstrate the join mechanics using derived fields.

print("\n" + "="*60)
print("Attribute Join: Adding Derived Fields")
print("="*60)

# Calculate area in km2 and attach to GeoDataFrame
gdf = gdf.copy()
gdf["area_km2"] = (gdf.to_crs(epsg=26913).geometry.area / 1e6).round(2)


def size_category(area_km2: float) -> str:
    """Classify district by geographic area for visualization."""
    if area_km2 < 200:
        return "small (<200 km²)"
    elif area_km2 < 1000:
        return "medium (200–1000 km²)"
    elif area_km2 < 3000:
        return "large (1000–3000 km²)"
    else:
        return "very large (>3000 km²)"


gdf["size_category"] = gdf["area_km2"].apply(size_category)

lookup = pd.DataFrame({
    "lg_id": gdf["lg_id"],
    "area_km2": gdf["area_km2"],
    "size_category": gdf["size_category"]
})

gdf_joined = gdf[["lg_id", "name", "geometry"]].merge(
    lookup, on="lg_id", how="left"
)

print(f"\nAttribute join on lg_id:")
print(f"  Base columns: lg_id, name, geometry")
print(f"  Joined columns: area_km2, size_category")
print(f"  Rows before: {len(gdf)} | Rows after: {len(gdf_joined)}")
print(f"  Nulls after join: {gdf_joined[['area_km2', 'size_category']].isnull().sum().to_string()}")
print(gdf_joined[["lg_id", "name", "area_km2", "size_category"]].head(5).to_string(index=False))

print("\nLargest 5 districts by area:")
print(gdf.nlargest(5, "area_km2")[["name", "area_km2", "mail_city"]].to_string(index=False))

print("\nSmallest 5 districts by area:")
print(gdf.nsmallest(5, "area_km2")[["name", "area_km2", "mail_city"]].to_string(index=False))


# ── STEP 6: PLOT ──────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("Plotting")
print("="*60)

color_map = {
    "small (<200 km²)":        "#2166ac",
    "medium (200–1000 km²)":   "#74add1",
    "large (1000–3000 km²)":   "#fdae61",
    "very large (>3000 km²)":  "#d73027",
}
gdf["color"] = gdf["size_category"].map(color_map)

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
for category, color in color_map.items():
    subset = gdf[gdf["size_category"] == category]
    if len(subset) > 0:
        subset.plot(ax=ax, facecolor=color, edgecolor="black",
                    linewidth=0.3, alpha=0.75)

legend_patches = [
    mpatches.Patch(facecolor=c, edgecolor="black", label=cat)
    for cat, c in color_map.items()
]
ax.legend(handles=legend_patches, loc="lower left",
          title="District Size", fontsize=9, title_fontsize=9)

ax.set_title(
    "Colorado School Board Districts: DOLA (State-submitted boundaries via SDRP, Aug 2024)\n"
    f"{len(gdf)} districts | Colored by geographic size",
    fontsize=12, pad=12
)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
plt.tight_layout()

output_path = "colorado_school_districts.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
logging.info(f"Plot saved: {output_path}")
print(f"Plot saved: {output_path}")
