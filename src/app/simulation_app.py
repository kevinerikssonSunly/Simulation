import io
import os
import sys
import streamlit as st
import pandas as pd
from io import BytesIO
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from simulation.simulate_dispatch import simulate_dispatch
from utils.data_prep import extract_from_file
from config import PROFILES_EE, PROFILES_LV, PROFILES_PL, PROFILES_LT, SIMULATION_INPUT
from utils.profiles import get_profiles

st.set_page_config(page_title="Sunly Baseload Simulator", layout="wide")

st.title("Sunly Baseload Simulation App")

st.sidebar.header("Simulation Settings")

run_button_manual = False
run_button_batch = False

profile_files = {
    "EE": PROFILES_EE,
    "LV": PROFILES_LV,
    "LT": PROFILES_LT,
    "PL": PROFILES_PL,
}

simulation_mode = st.sidebar.radio(
    "Select Simulation Mode",
    ["Manual Input", "Upload File (Batch Mode)"]
)

profile_type = st.sidebar.radio("Select country", list(profile_files.keys()))
profile_file = profile_files[profile_type]

container = st.container()

def validate_pair(name: str, capacity: int, price: int):
    if (capacity > 0 and price == 0) or (price > 0 and capacity == 0):
        st.error(f"⚠️ Both capacity and price must be > 0 for {name} if either is filled.")

with st.sidebar:
    with st.expander("Input field explanations"):
        st.markdown("**Grid Connection, MW** – Maximum power that can be exported to the grid at any given time.")

        st.markdown("**Wind Capacity, MW** – Installed wind generation capacity.")
        st.markdown("**Wind PaP price, EUR/MWh** – Contract price for wind energy (Power-as-Produced).")

        st.markdown("**Solar Capacity, MW – Installed solar (PV) generation capacity.")
        st.markdown("**PV PaP price, EUR/MWh** – Contract price for solar energy (Power-as-Produced).")

        st.markdown(f"**Target Baseload, MW** – Minimum constant power output target. Cannot exceed grid connection limit.")

        st.markdown("**Missing Energy Price EUR/MWh** – Penalty or replacement cost for unmet baseload demand.")

        st.markdown("---")
        st.markdown("### Battery Storage Settings")

        st.markdown("**BESS Xh Capacity MW** – Charge/discharge power capacity of the battery with X-hour duration.")
        st.markdown("**BESS Xh annual payment, EUR** – Annual fixed cost for the corresponding battery system.")
        st.markdown("A 2h BESS with 50 MW can store and release up to 100 MWh total.")
        st.markdown("Input is required for both capacity and cost to include each storage type.")

        st.markdown("**Pumped Hydro, MW** – Power capacity of pumped hydro storage system.")
        st.markdown("**Pumped Hydro annual payment, EUR** – Fixed yearly cost of the hydro storage system.")

        st.markdown("All BESS systems use 86% round-trip efficiency and Hydro Pump uses 90%.")

with st.sidebar:
    with st.expander("Results field explanations"):
        st.markdown("**Simulation id** – Identifier for the simulation run (can be used to group multiple results).")
        st.markdown("**Year** – Simulation year this result corresponds to.")

        st.markdown(
            "**BL 1, EUR/MWh** – Effective cost of delivered baseload, including storage and missing energy valued at VWAP (Volume Weighted Average Price).")
        st.markdown(
            "**BL 2, EUR/MWh** – Same as BL 1 but missing energy priced at a fixed penalty value instead of VWAP (Volume Weighted Average Price).")

        st.markdown(
            "**Break-even 1, EUR/MWh** – Required price to break even based on production, storage cost, excess sellback, and missing energy cost (fixed price).")
        st.markdown("**Break-even 2, EUR/MWh** – Same as Break-even 1, but uses VWAP for missing energy pricing.")

        st.markdown("**Annual avg spot, EUR/MWh** – Average day-ahead market price over the simulation year.")
        st.markdown(
            "**Res share in BL, %** – Share of baseload met by renewable energy (wind + solar + storage) as a percentage.")
        st.markdown("**Nr of green BL hours, h** – Number of hours when baseload demand was fully met.")
        st.markdown("**Nr of hours, h** – Total number of hours in the simulated year.")

        st.markdown(
            "**Wind cap price, EUR/MWh** – VWAP (volume-weighted average price) of wind energy sent to the grid.")
        st.markdown("**PV cap price, EUR/MWh** – VWAP of solar (PV) energy sent to the grid.")
        st.markdown(
            "**Missing energy VWAP, EUR/MWh** – Average spot price at which baseload shortfalls (missing energy) occurred.")
        st.markdown(
            "**Excess energy VWAP, EUR/MWh** – Average spot price for energy overproduced and exported to the grid.")

        st.markdown("**Baseload, MWh** – Total annual energy demand as determined by the baseload level (in MWh).")
        st.markdown(
            "**Overproduction share, %** – Share of produced energy (wind + solar) that was either curtailed or not used due to storage/grid limits.")

        st.markdown(
            "**Missing energy, MWh** – Total MWh of energy that was needed to meet baseload but could not be delivered.")
        st.markdown(
            "**Cycle loss, MWh** – Cumulative round-trip losses due to inefficiencies in charging/discharging storage systems.")

        st.markdown("**Wind prod, MWh** – Total annual energy produced by wind farms.")
        st.markdown("**Solar prod, MWh** – Total annual energy produced by solar panels.")
        st.markdown(
            "**Wind in BL, MWh** – Wind energy that was directly or indirectly (via storage) used to meet baseload.")
        st.markdown("**Solar in BL, MWh** – Same as above, but for solar energy.")

        st.markdown("**Excess wind, MWh** – Wind energy that was exported to the grid beyond baseload needs.")
        st.markdown("**Excess solar, MWh** – Solar energy exported to the grid beyond baseload needs.")
        st.markdown(
            "**Redundant wind, MWh** – Wind energy that could not be used or exported (e.g., due to grid/storage limits).")
        st.markdown("**Redundant solar, MWh** – Same as above, but for solar.")

        st.markdown(
            "**BESS Xh avg cycles** – Average daily full equivalent discharge cycles for the X-hour battery system.")
        st.markdown("**Hydro avg cycles** – Average daily full cycles for the pumped hydro storage system.")
if simulation_mode == "Manual Input":
    with st.sidebar:
        st.subheader("Manual Input")

        grid_connection = st.number_input("Grid Connection, MW", min_value=1)
        col1, col2 = st.columns(2)
        with col1:
            wind_cap = st.number_input("Wind Capacity, MW", min_value=0, value=0)
        with col2:
            wind_price = st.number_input("Wind PaP price EUR/MWh", min_value=0, value=0)

        col3, col4 = st.columns(2)
        with col3:
            solar_cap = st.number_input("Solar Capacity, MW", min_value=0, value=0)
        with col4:
            solar_price = st.number_input("PV PaP price EUR/MWh", min_value=0, value=0)

        col5, col6 = st.columns(2)
        with col5:
            baseload = st.number_input(f"Target Baseload MW, Min 1 - Max {grid_connection} MW", min_value=1, max_value=grid_connection, value=1)
        with col6:
            missing_energy_price = st.number_input("Missing Energy Price EUR/MWh", min_value=0, value=0)

        with st.expander("Battery Storage Settings"):
            col1, col2 = st.columns(2)
            with col1:
                battery_1h = st.number_input("1h Battery Capacity MW", min_value=0, value=0)
            with col2:
                battery_1h_price = st.number_input("BESS 1h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 1h", battery_1h, battery_1h_price)

            col3, col4 = st.columns(2)
            with col3:
                battery_2h = st.number_input("2h Battery Capacity, MW", min_value=0, value=0)
            with col4:
                battery_2h_price = st.number_input("BESS 2h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 2h", battery_2h, battery_2h_price)

            col5, col6 = st.columns(2)
            with col5:
                battery_4h = st.number_input("4h Battery Capacity, MW", min_value=0, value=0)
            with col6:
                battery_4h_price = st.number_input("BESS 4h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 4h", battery_4h, battery_4h_price)

            col7, col8 = st.columns(2)
            with col7:
                battery_6h = st.number_input("6h Battery Capacity, MW", min_value=0, value=0)
            with col8:
                battery_6h_price = st.number_input("BESS 6h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 6h", battery_6h, battery_6h_price)

            col9, col10 = st.columns(2)
            with col9:
                battery_8h = st.number_input("8h Battery Capacity, MW", min_value=0, value=0)
            with col10:
                battery_8h_price = st.number_input("BESS 8h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 8h", battery_8h, battery_8h_price)

            col11, col12 = st.columns(2)
            with col11:
                hydro_storage = st.number_input("Hydro Storage, MW", min_value=0, value=0)
            with col12:
                hydro_storage_price = st.number_input("Pumped Hydro annual payment, EUR", min_value=0, value=0)
            validate_pair("Pumped Hydro", hydro_storage, hydro_storage_price)

        run_button_manual = st.button("Run Simulation")

elif simulation_mode == "Upload File (Batch Mode)":
    with st.sidebar:
        with open(SIMULATION_INPUT, "rb") as f:
            st.download_button(
                label="📥 Download Simulation Input Template",
                file_name="simulation_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                data=f.read()
            )

        st.subheader("Upload File (Batch Mode)")
        uploaded_file = st.file_uploader("Choose a file to upload")
        run_button_batch = st.button("Run Simulation")

def summarize_by_price_step(df: pd.DataFrame, price_col: str = "Spot", step: int = 5) -> pd.DataFrame:
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

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def plot_energy_stack(df, baseload_value):
    df_plot = df.copy()
    df_plot = df_plot[["produced_energy", "battery_discharged", "missing_energy"]].copy()

    # Fill missing values
    for col in df_plot.columns:
        df_plot[col] = df_plot[col].fillna(0)

    # Add baseload
    df_plot["baseload"] = baseload_value

    # Resample to daily averages
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot stack
    ax.stackplot(
        df_plot.index,
        df_plot["produced_energy"],
        df_plot["battery_discharged"],
        df_plot["missing_energy"],
        labels=["Direct Production", "Battery Discharge", "Missing Energy"],
        alpha=0.8
    )

    # Step line for baseload
    ax.step(df_plot.index, df_plot["baseload"], where='mid', color="black", linestyle="--", label="Baseload")

    # Axes formatting
    ax.set_ylabel("Average Power (MW)")
    ax.set_title(f"Daily Avg Energy Supply vs Baseload – {df_plot.index[0].year}", fontsize=14)

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    plt.xticks(rotation=0)

    ax.legend(loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.4)

    return fig
if run_button_batch:
    with st.spinner("Running simulation..."):
        if uploaded_file:
            input_rows = extract_from_file(uploaded_file)
            input_rows = input_rows.fillna(0)
            all_results = []
            k = 1

            for i, row in input_rows.iterrows():
                grid_connection = row["grid_connection"]
                wind_cap = row["wind_cap"]
                solar_cap = row["solar_cap"]
                baseload = row["baseload"]
                wind_price = row["wind_price"]
                solar_price = row["solar_price"]
                battery_1h_price = row["battery_1h_price"]
                battery_2h_price = row["battery_2h_price"]
                battery_4h_price = row["battery_4h_price"]
                battery_6h_price = row["battery_6h_price"]
                battery_8h_price = row["battery_8h_price"]
                hydro_storage_price = row["hydro_storage_price"]
                missing_energy_price = row["missing_energy_price"]
                battery_1h = row["battery_1h_mw"]
                battery_2h = row["battery_2h_mw"]
                battery_4h = row["battery_4h_mw"]
                battery_6h = row["battery_6h_mw"]
                battery_8h = row["battery_8h_mw"]
                hydro_storage = row["hydro_mw"]
                bess_rte = 0.86
                hydro_rte = 0.9

                wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)

                results, _ = simulate_dispatch(
                    profile_file, grid_connection, wind_prod, solar_prod, baseload, wind_cap, solar_cap,
                    wind_price, solar_price, battery_1h_price, battery_2h_price, battery_4h_price,
                    battery_6h_price, battery_8h_price, hydro_storage_price, missing_energy_price,
                    battery_1h, battery_2h, battery_4h, battery_6h, battery_8h, hydro_storage,
                    bess_rte=bess_rte, hydro_rte=hydro_rte, simulation_id=k
                )
                k += 1
                all_results.extend(results)

            result_df = pd.DataFrame(all_results)
            st.success("✅ Batch simulation complete!")

            excel_buffer = io.BytesIO()
            result_df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            st.download_button(
                label="📥 Download Batch Results as EXCEL",
                data=excel_buffer,
                file_name="batch_simulation_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.dataframe(result_df)

elif run_button_manual:
    with st.spinner("Running simulation..."):

        wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)
        results, yearly_df = simulate_dispatch(
            profile_file, grid_connection, wind_prod, solar_prod, baseload, wind_cap, solar_cap,
            wind_price, solar_price, battery_1h_price, battery_2h_price, battery_4h_price,
            battery_6h_price, battery_8h_price, hydro_storage_price, missing_energy_price,
            battery_1h, battery_2h, battery_4h, battery_6h, battery_8h, hydro_storage,
            bess_rte=0.86, hydro_rte=0.9
        )

        result_df = pd.DataFrame(results)
        st.success("✅ Simulation complete!")

        st.subheader("Annual Results")
        st.dataframe(result_df)

        # Calculate mean across all years (all rows) for each numeric column
        mean_df = result_df.mean(numeric_only=True).to_frame().T

        # Optionally, add a label to make it clear this is the overall mean
        mean_df = mean_df.drop(columns=["year", "Simulation id"])
        st.dataframe(mean_df)


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
                yearly_df_year = yearly_df[yearly_df.index.year == year]
                st.pyplot(plot_energy_stack(yearly_df_year, baseload_value=baseload))