"""Download every public input into data/. Safe to re-run: files already on disk are skipped.

Author: Vivek Mitra. No keys or logins are needed for any source.
"""
import os
import requests

UA = {"User-Agent": "Mozilla/5.0 (research download)"}
YEARS = range(1981, 2024)        # IMD rainfall years used by the model

FILES = {
    # India Flood Inventory (Saharia et al. 2021), Zenodo record 16994648, CC BY-NC 4.0
    "ifi/India_Flood_Inventory_v3.csv": "https://zenodo.org/api/records/16994648/files/India_Flood_Inventory_v3.csv/content",
    "ifi/District_FloodedArea.csv": "https://zenodo.org/api/records/16994648/files/District_FloodedArea.csv/content",
    # Central Water Commission: state-wise flood damage 1953-2020
    "cwc/flood-damage-data-merged.pdf": "https://cwc.gov.in/sites/default/files/flood-damage-data-merged.pdf",
    # General Insurance Council yearbook 2024-25 (state-wise and class-wise non-life premium)
    "irdai/GIC_Yearbook_2024-25.pdf": "https://www.gicouncil.in/Year-Book/GIC_Yearbook_2024-25.pdf",
    # PIB release 1941399: state-wise PMFBY gross premium and paid claims, 2016-17 to 2022-23
    "pmfby/pib_1941399.html": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1941399&reg=3&lang=2",
    # Census 2011 Primary Census Abstract by district (scraped from censusindia.gov.in, MIT)
    "census/pca-total.csv": "https://raw.githubusercontent.com/pigshell/india-census-2011/master/pca-total.csv",
    # DataMeet maps (CC BY 4.0): Census 2011 districts and the official India outline
    "maps/india-composite.geojson": "https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson",
}
for ext in ("shp", "shx", "dbf", "prj"):
    FILES[f"maps/2011_Dist.{ext}"] = f"https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/2011_Dist.{ext}"


def fetch(path, url, data=None, min_size=100):
    out = os.path.join("data", path)
    if os.path.exists(out) and os.path.getsize(out) >= min_size:
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    for attempt in range(3):
        try:
            r = (requests.post(url, data=data, headers=UA, timeout=(30, 120)) if data
                 else requests.get(url, headers=UA, timeout=(30, 120)))
            r.raise_for_status()
            if len(r.content) >= min_size:
                open(out, "wb").write(r.content)
                print("saved", out, len(r.content))
                return
        except requests.RequestException as e:
            print("retry", path, e)
    print("FAILED", path)


def imd_year(y):
    # IMD Pune 0.25 degree daily gridded rainfall, one binary file per year (the same request imdlib makes)
    fetch(f"imd/rain/{y}.grd", "https://imdpune.gov.in/cmpg/Griddata/rainfall.php", data={"rain": y}, min_size=25_000_000)


if __name__ == "__main__":
    for p, u in FILES.items():
        fetch(p, u)
    for y in YEARS:                      # one at a time: parallel requests stall on the IMD server
        imd_year(y)
