"""Step 7: the paper's three figures, drawn from the result files. Author: Vivek Mitra"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection

from common import CLEAN, RES, SITE, HERE

OUT = HERE / "paper/figures"
NAVY, AMBER, RED, GREY = "#1f4e8c", "#d97a1e", "#c43c2f", "#5a6472"


def fig_map():
    m = json.load(open(SITE / "data/india-flood-map.json", encoding="utf-8"))
    p = pd.read_csv(CLEAN / "district_years.csv").groupby("id").p.mean()
    top = {r["id"] for r in json.load(open(RES / "part_c.json"))["top20_districts"]}
    polys, vals, tops = [], [], []
    for i, rings in enumerate(m["districts"]):
        for r in rings:
            xy = np.array(r).reshape(-1, 2) / 100
            polys.append(xy)
            vals.append(p.get(i, np.nan))
            if i in top:
                tops.append(xy)
    fig, ax = plt.subplots(figsize=(6.2, 6.6))
    cmap = matplotlib.colormaps["Blues"].copy()
    cmap.set_bad("#e8e3d6")
    pc = PolyCollection(polys, array=np.ma.masked_invalid(vals), cmap=cmap, clim=(0, 0.6), edgecolor="white", linewidth=0.15)
    ax.add_collection(pc)
    ax.add_collection(PolyCollection(tops, facecolor="none", edgecolor=AMBER, linewidth=0.9))
    for r in m["outline"]:
        xy = np.array(r).reshape(-1, 2) / 100
        ax.plot(xy[:, 0], xy[:, 1], color="#18202b", linewidth=0.6)
    ax.set_xlim(67.5, 98); ax.set_ylim(6, 37.5); ax.set_aspect(1 / np.cos(np.radians(22))); ax.axis("off")
    cb = fig.colorbar(pc, ax=ax, shrink=0.5, pad=0.01)
    cb.set_label("average flood chance per monsoon, 1981-2023")
    fig.tight_layout(); fig.savefig(OUT / "map.png", dpi=200); plt.close(fig)


def fig_damage():
    t = pd.read_csv(RES / "a2_test_predictions.csv")
    t = t[t.target == "houses"]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.vlines(t.ly, t.lo, t.hi, color=NAVY, alpha=0.25, linewidth=2)
    ax.scatter(t.ly, t.base, s=14, color=GREY, marker="x", label="baseline: state average", zorder=3)
    ax.scatter(t.ly, t.pred, s=14, color=NAVY, label="model, with 80% range", zorder=4)
    lim = [min(t.ly.min(), t.lo.min()) - 0.5, max(t.ly.max(), t.hi.max()) + 0.5]
    ax.plot(lim, lim, color=RED, linewidth=0.8, label="perfect forecast")
    ticks = [(np.log(10 ** k), f"{10 ** k:,}") for k in range(0, 8) if lim[0] <= np.log(10 ** k) <= lim[1]]
    ax.set_xticks(*zip(*ticks)); ax.set_yticks(*zip(*ticks))
    ax.set_xlabel("houses damaged, reported (log scale)"); ax.set_ylabel("forecast (log scale)")
    ax.legend(fontsize=8, frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "damage.png", dpi=200); plt.close(fig)


def fig_gap():
    s = pd.DataFrame(json.load(open(RES / "part_c.json"))["states"]).head(15)[::-1]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.barh(s.state, s.gap, color=[AMBER if i == len(s) - 1 else NAVY for i in range(len(s))])
    ax.set_xlabel("people at flood risk per Rs 1 crore of fire + PMFBY premium")
    ax.spines[["top", "right"]].set_visible(False); ax.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(OUT / "gap.png", dpi=200); plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_map(); fig_damage(); fig_gap()
    print("  figures: paper/figures/map.png, damage.png, gap.png")
