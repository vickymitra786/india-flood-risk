"""Step 2: IMD 0.25-degree daily rainfall -> one row per district and monsoon year (June-September).

  rx3  wettest 3 days in a row (mm), district average
  tot  monsoon total (mm)
Writes data/clean/rain.csv. Author: Vivek Mitra
"""
import numpy as np
import pandas as pd
import shapefile
from shapely import STRtree, points
from shapely.geometry import shape

from common import DATA, CLEAN

LAT = 6.5 + 0.25 * np.arange(129)      # IMD grid (imdlib's layout)
LON = 66.5 + 0.25 * np.arange(135)


def read_year(y):
    """IMD binary file: little-endian float32, laid out day x lat x lon; -999 = no data.
    (Checked: identical to imdlib.open_data for 2018.)"""
    a = np.fromfile(DATA / f"imd/rain/{y}.grd", dtype="<f4")
    days = a.size // (129 * 135)
    assert days in (365, 366) and a.size == days * 129 * 135, f"{y}.grd is incomplete: run get_data.py again"
    a = a.reshape(days, 129, 135)                      # day, lat, lon
    return np.where(a < -900, np.nan, a), pd.date_range(f"{y}-01-01", periods=days)


def cell_weights():
    """Matrix W (districts x cells): each district averages the grid cells whose centre lies inside it.
    A district too small to hold a centre uses the cell nearest its centre point."""
    r = shapefile.Reader(str(DATA / "maps/2011_Dist.shp"))
    polys = [shape(s.__geo_interface__) for s in r.shapes()]
    lon, lat = np.meshgrid(LON, LAT)
    pts = points(lon.ravel(), lat.ravel())
    valid = ~np.isnan(read_year(2018)[0][180])          # cells IMD covers (any monsoon day)
    W = np.zeros((len(polys), pts.size))
    tree = STRtree(pts)
    for i, p in enumerate(polys):
        idx = [j for j in tree.query(p, predicate="contains") if valid.ravel()[j]]
        if not idx:
            c = p.representative_point()
            d = (lon.ravel() - c.x) ** 2 + (lat.ravel() - c.y) ** 2
            d[~valid.ravel()] = np.inf
            idx = [int(np.argmin(d))]
        W[i, idx] = 1 / len(idx)
    return W


if __name__ == "__main__":
    W = cell_weights()
    rows = []
    missing = [y for y in range(1981, 2024) if not (DATA / f"imd/rain/{y}.grd").exists()]
    if missing:
        print("  WARNING: IMD years not downloaded yet (run get_data.py again):", missing)
    for y in sorted(set(range(1981, 2024)) - set(missing)):
        a, days = read_year(y)
        m = (days.month >= 6) & (days.month <= 9)
        daily = W @ np.nan_to_num(a[m].reshape(m.sum(), -1)).T          # districts x monsoon days
        three = daily[:, :-2] + daily[:, 1:-1] + daily[:, 2:]
        for i in range(W.shape[0]):
            rows.append((i, y, round(three[i].max(), 1), round(daily[i].sum(), 1)))
    pd.DataFrame(rows, columns=["id", "year", "rx3", "tot"]).to_csv(CLEAN / "rain.csv", index=False)
    print(f"  rain features: {len(rows)} district-years")
