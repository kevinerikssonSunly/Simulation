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

container = st.container()

with st.sidebar:
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            wind_cap = st.number_input("Wind Capacity (MW)", min_value=0, value=0)
        with col2:
            wind_price = st.number_input("Wind PaP price EUR/MWh", min_value=0, value=0)

        col3, col4 = st.columns(2)
        with col3:
            solar_cap = st.number_input("Solar Capacity (MW)", min_value=0, value=0)
        with col4:
            solar_price = st.number_input("PV PaP price EUR/MWh", min_value=0, value=0)

        col5, col6 = st.columns(2)
        with col5:
            baseload = st.number_input("Target Baseload (MW), Min 1 - Max 183 MW", min_value=1, max_value=183, value=1)
        with col6:
            missing_energy_price = st.number_input("Missing Energy Price (MW)", min_value=0, value=0)
with st.sidebar.expander("Battery Storage Settings"):
    col1, col2 = st.columns(2)
    with col1:
        battery_1h = st.number_input("1h Battery Capacity (MW)", min_value=0, value=0)
    with col2:
        battery_1h_price = st.number_input("BESS 1h annual payment, EUR", min_value=0, value=0)
    col3, col4 = st.columns(2)
    with col3:
        battery_2h = st.number_input("2h Battery Capacity (MW)", min_value=0, value=0)
    with col4:
        battery_2h_price = st.number_input("BESS 2h annual payment, EUR", min_value=0, value=0)
    col5, col6 = st.columns(2)
    with col5:
        battery_4h = st.number_input("4h Battery Capacity (MW)", min_value=0, value=0)
    with col6:
        battery_4h_price = st.number_input("BESS 4h annual payment, EUR", min_value=0, value=0)
    col7, col8 = st.columns(2)
    with col7:
        battery_6h = st.number_input("6h Battery Capacity (MW)", min_value=0, value=0)
    with col8:
        battery_6h_price = st.number_input("BESS 6h annual payment, EUR", min_value=0, value=0)
    col9, col10 = st.columns(2)
    with col9:
        battery_8h = st.number_input("8h Battery Capacity (MW)", min_value=0, value=0)
    with col10:
        battery_8h_price = st.number_input("BESS 8h annual payment, EUR", min_value=0, value=0)
    col11, col12 = st.columns(2)
    with col11:
        hydro_storage = st.number_input("Hydro Storage (MW)", min_value=0, value=0)
    with col12:
        hydro_storage_price = st.number_input("Pumped Hydro annual payment, EUR", min_value=0, value=0)

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

    df["year"] = df.index.year
    df["price_bin"] = (df[price_col] // step) * step

    summary = (
        df.groupby(["year", "price_bin"])[["missing_energy", "excess_energy"]]
        .mean()
        .reset_index()
        .sort_values(["year", "price_bin"])
    )
    return summary

if run_button:
    with st.spinner("Running simulation..."):

        wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)

        results, yearly_df = simulate_dispatch_per_year(
            profile_file, wind_prod, solar_prod, baseload, wind_cap, solar_cap,
            wind_price, solar_price, battery_1h_price, battery_2h_price, battery_4h_price, battery_6h_price, battery_8h_price, hydro_storage_price, missing_energy_price,
            battery_1h, battery_2h, battery_4h, battery_6h, battery_8h, hydro_storage, bess_rte=0.86, hydro_rte=0.9)

        result_df = pd.DataFrame(results)

        st.success("Simulation complete!")
        st.subheader("Annual Results")
        st.dataframe(result_df)

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
                st.markdown("Missing Energy")
                st.bar_chart(year_data["missing_energy"])
                st.markdown("Excess Energy")
                st.bar_chart(year_data["excess_energy"])
else:
    st.info("Please fill fields to begin.")

