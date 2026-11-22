"""Reproduce every number on vivekmitra.com/india-flood.html and in the paper.

    python get_data.py     (once: downloads the public inputs into data/)
    python run_all.py

rainfall -> district flood forecast and state damage (Part A) -> crop claims (Part B)
-> protection gap (Part C) -> site files, figures, checks, and the paper.
Results go to results/. Website files go to ../../site when this repo sits inside the vivekmitra.com
folder, else to site_data/. Nothing is written anywhere else.
Author: Vivek Mitra
"""
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["step1_tables.py", "step2_rain.py", "step3_damage.py", "step4_claims.py",
         "step5_gap.py", "step6_site.py", "step7_figures.py", "test_check.py"]

if __name__ == "__main__":
    missing = [y for y in range(1981, 2024) if not (HERE / f"data/imd/rain/{y}.grd").exists()]
    if missing:
        sys.exit(f"IMD rainfall missing for {missing}: run python get_data.py first")
    sys.path.insert(0, str(HERE))
    for s in STEPS:
        t = time.time()
        print(f"== {s}")
        runpy.run_path(str(HERE / s), run_name="__main__")
        print(f"   ({time.time() - t:.0f} s)")

    # The paper: Node builds the .docx from results/, Word (Windows) converts it to PDF, then a check.
    paper = HERE / "paper"
    if shutil.which("node") is None:
        sys.exit("Node.js not found: results and site files are done; install Node 22 to build the paper")
    print("== paper")
    if not (paper / "node_modules/docx").exists():
        subprocess.run("npm ci --silent", cwd=paper, shell=True, check=True)
    subprocess.run(["node", "build_paper.js"], cwd=paper, check=True)
    if sys.platform == "win32":
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "to_pdf.ps1"], cwd=paper, check=True)
    else:
        print("  PDF step skipped: it needs Microsoft Word on Windows (the .docx is built)")
    runpy.run_path(str(HERE / "check_paper.py"), run_name="__main__")
