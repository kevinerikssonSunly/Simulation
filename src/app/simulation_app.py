import os
import sys
import streamlit as st
import pandas as pd
from io import BytesIO

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from config import PROFILES_EE, PROFILES_LV, PROFILES_PL, PROFILES_LT
from utils.profiles import get_profiles

from optimisation.search import simulate_dispatch_per_year

st.set_page_config(page_title="Sunly Baseload Simulator", layout="wide")

st.title("Sunly Baseload Simulation App")

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

def summarize_by_price_step(df: pd.DataFrame, price_col: str = "Spot", step: int = 5) -> pd.DataFrame:
    """
    Summarizes average missing and wasted energy grouped by year and fixed Spot price intervals.

    Args:
        df (pd.DataFrame): DataFrame with columns "Spot", "missing_energy", "wasted_energy"
                           and a datetime index.
        price_col (str): Column name for price (default is "Spot").
        step (int): Step size in euros for price binning (default is 5€ bins).

    Returns:
        pd.DataFrame: Multi-year summary with average missing/wasted energy by year and price bin.
    """
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex.")

    # Extract year and price bin
    df["year"] = df.index.year
    df["price_bin"] = (df[price_col] // step) * step

    # Group by year and price bin, compute averages
    summary = (
        df.groupby(["year", "price_bin"])[["missing_energy", "wasted_energy"]]
        .mean()
        .reset_index()
        .sort_values(["year", "price_bin"])
    )

    return summary

if run_button:
    with st.spinner("Running simulation..."):

        wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)

        results, yearly_df = simulate_dispatch_per_year(profile_file, wind_prod, solar_prod, baseload, wind_cap, solar_cap,
                                             battery_1h, battery_2h, battery_4h, battery_6h, battery_8h, hydro_storage, bess_rte=0.86, hydro_rte=0.9)

        result_df = pd.DataFrame(results)

        st.success("Simulation complete!")
        st.subheader("Annual Results")
        st.dataframe(result_df)

        # --- Downloadable CSV ---
        csv_buffer = BytesIO()
        result_df.to_csv(csv_buffer, index=False)
        st.download_button("📥 Download Results as CSV", data=csv_buffer.getvalue(), file_name="simulation_results.csv")

        summary_df = summarize_by_price_step(yearly_df)

        tab_titles = [f"Year {year}" for year in summary_df["year"].unique()]
        tabs = st.tabs(tab_titles)

        for tab, year in zip(tabs, summary_df["year"].unique()):
            with tab:
                st.subheader(f"Charts for Year {year}")
                year_data = summary_df[summary_df["year"] == year].set_index("price_bin")
                st.bar_chart(year_data["missing_energy"])
                st.bar_chart(year_data["wasted_energy"])
else:
    st.info("Please fill fields to begin.")

