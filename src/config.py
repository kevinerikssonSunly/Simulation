from pathlib import Path

# Go from /src/config.py → project root → /data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Profiles
PROFILES_EE = DATA_DIR / "profiles_EE.xlsx"
PROFILES_LV = DATA_DIR / "profiles_LV.xlsx"
PROFILES_LT = DATA_DIR / "profiles_LT.xlsx"
PROFILES_PL = DATA_DIR / "profiles_PL.xlsx"

# Yields
YIELD_EE = DATA_DIR / "YIELD_EE.xlsx"
YIELD_LV = DATA_DIR / "YIELD_LV.xlsx"
YIELD_LT = DATA_DIR / "YIELD_LT.xlsx"
YIELD_PL = DATA_DIR / "YIELD_PL.xlsx"

# Raw PV/Wind production (optional)
PV_WIND_PROD_EE = DATA_DIR / "PV_WIND_PROD_EE.xlsx"
PV_WIND_PROD_LV = DATA_DIR / "PV_WIND_PROD_LV.xlsx"
PV_WIND_PROD_LT = DATA_DIR / "PV_WIND_PROD_LT.xlsx"
PV_WIND_PROD_PL = DATA_DIR / "PV_WIND_PROD_PL.xlsx"