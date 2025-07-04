import os
import sys

from config import PROFILES_EE, PROFILES_LV, PROFILES_PL, PROFILES_LT
from utils.profiles import get_profiles

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))  # = /.../green_baseload_sim/src

# Add src to the path if not already included
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import streamlit as st
import pandas as pd
from io import BytesIO

from optimisation.search import simulate_dispatch_per_year

st.set_page_config(page_title="Green Baseload Simulator", layout="wide")

st.title("Green Baseload Simulation App")

# --- Sidebar Inputs ---
st.sidebar.header("Simulation Settings")

profile_files = {
    "EE": PROFILES_EE,
    "LV": PROFILES_LV,
    "LT": PROFILES_LT,
    "PL": PROFILES_PL,
}

profile_type = st.sidebar.radio("Select country", list(profile_files.keys()))
profile_file = profile_files[profile_type]

wind_cap = st.sidebar.number_input("Wind Capacity (MW)", min_value=0, value=0)
solar_cap = st.sidebar.number_input("Solar Capacity (MW)", min_value=0, value=0)
baseload = st.sidebar.number_input("Target Baseload (MW)", min_value=1, value=1)

with st.sidebar.expander("Battery Storage Settings"):
    battery_1h = st.number_input("1h Battery Capacity (MW)", min_value=0, value=0)
    battery_2h = st.number_input("2h Battery Capacity (MW)", min_value=0, value=0)
    battery_4h = st.number_input("4h Battery Capacity (MW)", min_value=0, value=0)
    battery_6h = st.number_input("6h Battery Capacity (MW)", min_value=0, value=0)
    battery_8h = st.number_input("8h Battery Capacity (MW)", min_value=0, value=0)
    hydro_storage = st.number_input("Hydro Storage (MW)", min_value=0, value=0)


run_button = st.sidebar.button("Run Simulation")

if run_button:
    with st.spinner("Running simulation..."):

        wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)

        results = simulate_dispatch_per_year(wind_prod, solar_prod, baseload, wind_cap, solar_cap,
                                             battery_1h, battery_2h, battery_4h, battery_6h, battery_8h, hydro_storage, bess_rte=0.86, hydro_rte=0.9)

        result_df = pd.DataFrame(results)

        st.success("Simulation complete!")
        st.subheader("Annual Results")
        st.dataframe(result_df)

        # --- Downloadable CSV ---
        csv_buffer = BytesIO()
        result_df.to_csv(csv_buffer, index=False)
        st.download_button("📥 Download Results as CSV", data=csv_buffer.getvalue(), file_name="simulation_results.csv")

else:
    st.info("Please fill fields to begin.")