"""Shared paths and name cleaning. Author: Vivek Mitra."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CLEAN = DATA / "clean"          # tables rebuilt by the pipeline
RES = HERE / "results"          # every number the site and the paper use
# Website files go to the vivekmitra.com site folder when this repo sits inside it, else to site_data/.
SITE = HERE.parent.parent / "site" if (HERE.parent.parent / "site/index.html").exists() else HERE / "site_data"

TRAIN_END = 2012                # fit on years up to 2012, test on 2013 onwards

# One name per state. Telangana is merged into Andhra Pradesh and Ladakh into
# Jammu & Kashmir, because the CWC damage series reports them that way for most years.
STATES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
          "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala",
          "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
          "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Tripura", "Uttar Pradesh", "Uttarakhand",
          "West Bengal", "Andaman & Nicobar", "Chandigarh", "Dadra & Nagar Haveli", "Daman & Diu",
          "Delhi", "Lakshadweep", "Puducherry"]
ALIAS = {"telangana": "Andhra Pradesh", "ladakh": "Jammu & Kashmir", "arunanchalpradesh": "Arunachal Pradesh",
         "chattisgarh": "Chhattisgarh", "madhyapraadesh": "Madhya Pradesh", "orissa": "Odisha",
         "andamannicobarisland": "Andaman & Nicobar", "andamannicobarislands": "Andaman & Nicobar",
         "andmannicobarislands": "Andaman & Nicobar", "anisland": "Andaman & Nicobar",
         "anislands": "Andaman & Nicobar", "andamannicobaris": "Andaman & Nicobar",
         "dadaranagarhavelli": "Dadra & Nagar Haveli", "dadarnagarhaveli": "Dadra & Nagar Haveli",
         "dadranagrahaveli": "Dadra & Nagar Haveli", "dnhavelidamandiu": "Dadra & Nagar Haveli",
         "daman": "Daman & Diu", "diu": "Daman & Diu", "nctofdelhi": "Delhi", "newdelhi": "Delhi",
         "uttaranchal": "Uttarakhand", "puduchcherry": "Puducherry", "pondicherry": "Puducherry",
         "madras": "Tamil Nadu", "tamilnadu": "Tamil Nadu", "eastrajasthan": "Rajasthan",
         "partsofmaharashtra": "Maharashtra", "uttarpradesh": "Uttar Pradesh"}


def key(s):
    """Lower-case letters only, without the word 'and': 'Jammu and Kashmir' -> 'jammukashmir'."""
    return re.sub(r"[^a-z]", "", re.sub(r"\band\b|&", "", str(s).lower()))


STATE_KEY = {key(s): s for s in STATES} | ALIAS


def state(s):
    """Canonical state name, or None if the text is not a state."""
    return STATE_KEY.get(key(s))
