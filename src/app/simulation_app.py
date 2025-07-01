import os
import sys
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))  # = /.../green_baseload_sim/src

# Add src to the path if not already included
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

from models.resource import Wind, PV
from optimisation.search import simulate_dispatch_per_year
from utils.data_prep import load_profiles

st.set_page_config(page_title="Green Baseload Simulator", layout="wide")

st.title("⚡ Green Baseload Simulation App")

# --- Sidebar Inputs ---
st.sidebar.header("Simulation Settings")

wind_cap = st.sidebar.number_input("Wind Capacity (MW)", min_value=0, value=500, step=50)
solar_cap = st.sidebar.number_input("Solar Capacity (MW)", min_value=0, value=500, step=50)
baseload = st.sidebar.number_input("Target Baseload (MW)", min_value=1, value=250, step=25)

uploaded_hourly = st.sidebar.file_uploader("Upload Hourly Production XLSX", type=["xlsx"])
uploaded_yearly = st.sidebar.file_uploader("Upload Yearly Production XLSX", type=["xlsx"])

run_button = st.sidebar.button("Run Simulation")

# --- Main Area ---
if run_button and uploaded_hourly and uploaded_yearly:
    with st.spinner("Running simulation..."):

        df_profiles = load_profiles(uploaded_hourly, uploaded_yearly)
        wind_profile = df_profiles['wind_profile']
        solar_profile = df_profiles['solar_profile']

        wind = Wind(wind_cap, wind_profile)
        solar = PV(solar_cap, solar_profile)

        wind_prod = wind.get_production()
        solar_prod = solar.get_production()

        results = simulate_dispatch_per_year(wind_prod, solar_prod, baseload, wind_cap, solar_cap)

        result_df = pd.DataFrame(results)

        st.success("Simulation complete!")
        st.subheader("📊 Annual Results")
        st.dataframe(result_df)

        # --- Downloadable CSV ---
        csv_buffer = BytesIO()
        result_df.to_csv(csv_buffer, index=False)
        st.download_button("📥 Download Results as CSV", data=csv_buffer.getvalue(), file_name="simulation_results.csv")

        # --- Visualization ---
        st.subheader("📈 Green Energy Share by Year")
        fig, ax = plt.subplots()
        ax.bar(result_df["year"], result_df["green_energy_share"])
        ax.set_ylabel("Green Energy Share (%)")
        ax.set_xlabel("Year")
        ax.set_title("Annual Green Energy Share")
        st.pyplot(fig)

else:
    st.info("Please upload both wind and solar datasets to begin.")