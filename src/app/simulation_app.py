import io
import os
import sys
import streamlit as st
import pandas as pd
from io import BytesIO
import numpy as np
import altair as alt

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
    "LV - NB! Solar data from 2024": PROFILES_LV,
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
def plot_energy_stack_st_altair(df, baseload_value):
    df_plot = df.copy()
    df_plot = df_plot[["produced_energy", "battery_discharged", "battery_charged"]].fillna(0)
    df_plot["baseload"] = baseload_value

    df_plot["direct_to_bl"] = np.minimum(df_plot["produced_energy"], df_plot["baseload"])

    df_plot["battery_to_bl"] = np.minimum(
        df_plot["baseload"] - df_plot["direct_to_bl"],
        df_plot["battery_discharged"]
    )

    df_plot["missing_to_bl"] = df_plot["baseload"] - df_plot["direct_to_bl"] - df_plot["battery_to_bl"]

    surplus = df_plot["produced_energy"] - df_plot["direct_to_bl"]
    df_plot["charged_to_battery"] = np.minimum(surplus, df_plot["battery_charged"]).clip(lower=0)

    df_plot["excess_energy"] = (df_plot["produced_energy"]
                                - df_plot["direct_to_bl"]
                                - df_plot["charged_to_battery"]).clip(lower=0)

    df_plot_for_chart = pd.DataFrame({
        "Direct Production": df_plot["direct_to_bl"],
        "Battery Discharge": df_plot["battery_to_bl"],
        "Missing Energy": df_plot["missing_to_bl"],
        "Charged to Battery": df_plot["charged_to_battery"],
        "Excess Energy": df_plot["excess_energy"]
    })

    df_plot_for_chart.columns = [
        "Direct Production",
        "Battery Discharge",
        "Missing Energy",
        "Charged to Battery",
        "Excess Energy"
    ]
    df_plot_for_chart["Date"] = df_plot.index

    df_melt = df_plot_for_chart.melt(id_vars="Date", var_name="Source", value_name="Value")

    category_order = [
        "Direct Production",
        "Battery Discharge",
        "Missing Energy",
        "Charged to Battery",
        "Excess Energy"
    ]

    color_mapping = {
        "Direct Production": "#1f77b4",  # Blue
        "Battery Discharge": "orange",
        "Missing Energy": "red",
        "Charged to Battery": "green",
        "Excess Energy": "#9467bd"  # Purple
    }

    df_melt["Source"] = pd.Categorical(df_melt["Source"], categories=category_order, ordered=True)

    df_melt["sort_index"] = df_melt["Source"].cat.codes

    chart = alt.Chart(df_melt).mark_bar(size=1).encode(
        x=alt.X("Date:T", title="Date"),
        y=alt.Y("Value:Q", stack="zero", title="Average Power (MW)"),
        color=alt.Color("Source:N",
                        scale=alt.Scale(domain=category_order,
                                        range=[color_mapping[k] for k in category_order]), legend=None),
        order=alt.Order('sort_index:Q'),
        tooltip=["Date:T", "Source:N", "Value:Q"]
    ).properties(
        width=400,
        height=400
    ).interactive()

    # Legend
    st.markdown("**Daily Energy Supply vs Baseload**")

    st.markdown("""
    <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 10px;">
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: #1f77b4; margin-right: 5px; border-radius: 2px;"></div>
            <span style="font-size: 14px;">Direct Production</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: orange; margin-right: 5px; border-radius: 2px;"></div>
            <span style="font-size: 14px;">Battery Discharge</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: red; margin-right: 5px; border-radius: 2px;"></div>
            <span style="font-size: 14px;">Missing Energy</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: green; margin-right: 5px; border-radius: 2px;"></div>
            <span style="font-size: 14px;">Charged to Battery</span>
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 15px; height: 15px; background-color: #9467bd; margin-right: 5px; border-radius: 2px;"></div>
            <span style="font-size: 14px;">Excess Energy</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return chart

with st.sidebar:
    with st.expander("Input field explanations"):

        st.markdown("**Wind Capacity, MW** – Installed wind generation capacity.")
        st.markdown("**Wind PaP price, EUR/MWh** – Contract price for wind energy (Pay-as-Produced).")

        st.markdown("**Solar Capacity, MW** – Installed solar (PV) generation capacity.")
        st.markdown("**PV PaP price, EUR/MWh** – Contract price for solar energy (Pay-as-Produced).")

        st.markdown(f"**Target Baseload, MW** – Minimum constant power output target.")

        st.markdown("**Missing Energy Price EUR/MWh** – Penalty or replacement cost for unmet baseload demand.")



        st.markdown("---")
        st.markdown("### Battery Storage Settings")

        st.markdown("**BESS Xh Capacity MW** – Charge/discharge power capacity of the battery with X-hour duration.")
        st.markdown("**BESS Xh annual payment, EUR** – Annual fixed cost for the corresponding battery system.")
        st.markdown("A 2h BESS with 50 MW can store and release up to 100 MWh total.")
        st.markdown("Input is required for both capacity and cost to include each storage type.")

        st.markdown("All BESS systems use 86% round-trip efficiency.")
with st.sidebar:
    with st.expander("Output field explanations"):
        st.markdown("**Simulation id** – Identifier for the simulation run (can be used to group multiple results).")
        st.markdown("**Year** – Simulation year this result corresponds to.")

        st.markdown(
            "**BL 1 - Fixed Missing, EUR/MWh** – Effective cost of delivered baseload, including storage and missing energy valued at VWAP (Volume Weighted Average Price).")
        st.markdown(
            "**BL 2 - VWAP Missing, EUR/MWh** – Same as BL 1 but missing energy priced at a fixed penalty value instead of VWAP (Volume Weighted Average Price).")

        st.markdown("**Break-even 1 - Fixed Missing, EUR/MWh** – Required price to break even based on production, storage cost, wind and solar sellback, and missing energy cost (fixed price).")
        st.markdown("**Break-even 2 - VWAP Missing, EUR/MWh** – Same as Break-even 1, but uses VWAP for missing energy pricing.")

        st.markdown("**Annual avg spot, EUR/MWh** – Average day-ahead market price over the simulation year.")
        st.markdown("**Res share in BL, %** – Share of baseload met by renewable energy (wind + solar + storage) as a percentage.")
        st.markdown("**Nr of green BL hours, h** – Number of hours when baseload demand was fully met.")
        st.markdown("**Nr of hours, h** – Total number of hours in the simulated year.")

        st.markdown("**Wind cap price, EUR/MWh** – VWAP (volume-weighted average price) of wind energy sent to the grid.")
        st.markdown("**PV cap price, EUR/MWh** – VWAP of solar (PV) energy sent to the grid.")
        st.markdown("**Missing energy VWAP, EUR/MWh** – Average spot price at which baseload shortfalls (missing energy) occurred.")
        st.markdown("**Excess energy VWAP, EUR/MWh** – Average spot price for energy overproduced and exported to the grid.")

        st.markdown("**Baseload, MWh** – Total annual energy demand as determined by the baseload level (in MWh).")
        st.markdown("**Overproduction share, %** – Share of produced energy (wind + solar) that was either curtailed or not used due to storage/grid limits.")

        st.markdown("**Missing energy, MWh** – Total MWh of energy that was needed to meet baseload but could not be delivered.")
        st.markdown("**Cycle loss, MWh** – Cumulative round-trip losses due to inefficiencies in charging/discharging storage systems.")

        st.markdown("**Wind prod, MWh** – Total annual energy produced by wind farms.")
        st.markdown("**Solar prod, MWh** – Total annual energy produced by solar panels.")
        st.markdown("**Wind in BL, MWh** – Wind energy that was directly or indirectly (via storage) used to meet baseload.")
        st.markdown("**Solar in BL, MWh** – Same as above, but for solar energy.")

        st.markdown("**Excess wind, MWh** – Wind energy that was exported to the grid beyond baseload needs.")
        st.markdown("**Excess solar, MWh** – Solar energy exported to the grid beyond baseload needs.")

        st.markdown("**BESS Xh avg cycles** – Average daily full equivalent discharge cycles for the X-hour battery system.")

if simulation_mode == "Manual Input":
    with st.sidebar:
        st.subheader("Manual Input")

        col1, col2 = st.columns(2)
        with col1:
            wind_cap = st.number_input("Wind Capacity, MW", min_value=0, value=0)
        with col2:
            wind_price = st.number_input("Wind PaP Price, EUR/MWh", min_value=0, value=0)

        col3, col4 = st.columns(2)
        with col3:
            solar_cap = st.number_input("PV Capacity, MW", min_value=0, value=0)
        with col4:
            solar_price = st.number_input("PV PaP Price, EUR/MWh", min_value=0, value=0)

        col5, col6 = st.columns(2)
        with col5:
            baseload = st.number_input(f"Target Baseload MW, Min 1 MW", min_value=1, value=1)
        with col6:
            missing_energy_price = st.number_input("Missing Energy Price, EUR/MWh", min_value=0, value=0)

        with st.expander("Battery Storage Settings"):
            col1, col2 = st.columns(2)
            with col1:
                battery_1h_mw = st.number_input("1h Battery Capacity, MW", min_value=0, value=0)
            with col2:
                battery_1h_price = st.number_input("BESS 1h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 1h", battery_1h_mw, battery_1h_price)

            col3, col4 = st.columns(2)
            with col3:
                battery_2h_mw = st.number_input("2h Battery Capacity, MW", min_value=0, value=0)
            with col4:
                battery_2h_price = st.number_input("BESS 2h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 2h", battery_2h_mw, battery_2h_price)

            col5, col6 = st.columns(2)
            with col5:
                battery_4h_mw = st.number_input("4h Battery Capacity, MW", min_value=0, value=0)
            with col6:
                battery_4h_price = st.number_input("BESS 4h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 4h", battery_4h_mw, battery_4h_price)

            col7, col8 = st.columns(2)
            with col7:
                battery_6h_mw = st.number_input("6h Battery Capacity, MW", min_value=0, value=0)
            with col8:
                battery_6h_price = st.number_input("BESS 6h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 6h", battery_6h_mw, battery_6h_price)

            col9, col10 = st.columns(2)
            with col9:
                battery_8h_mw = st.number_input("8h Battery Capacity, MW", min_value=0, value=0)
            with col10:
                battery_8h_price = st.number_input("BESS 8h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 8h", battery_8h_mw, battery_8h_price)

            col11, col12 = st.columns(2)
            with col11:
                battery_12h_mw = st.number_input("12h Battery Capacity, MW", min_value=0, value=0)
            with col12:
                battery_12h_price = st.number_input("BESS 12h annual payment, EUR", min_value=0, value=0)
            validate_pair("BESS 12h", battery_12h_mw, battery_12h_price)

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

if run_button_batch:
    with st.spinner("Running simulation..."):
        if uploaded_file:
            input_rows = extract_from_file(uploaded_file)
            input_rows = input_rows.fillna(0)
            all_results = []
            k = 1

            for i, row in input_rows.iterrows():
                wind_cap = row["wind_cap"]
                solar_cap = row["solar_cap"]
                baseload = row["baseload"]
                wind_price = row["wind_price"]
                solar_price = row["solar_price"]
                missing_energy_price = row["missing_energy_price"]
                battery_1h_price = row["battery_1h_price"]
                battery_2h_price = row["battery_2h_price"]
                battery_4h_price = row["battery_4h_price"]
                battery_6h_price = row["battery_6h_price"]
                battery_8h_price = row["battery_8h_price"]
                battery_12h_price = row["battery_12h_price"]
                battery_1h_mw = row["battery_1h_mw"]
                battery_2h_mw = row["battery_2h_mw"]
                battery_4h_mw = row["battery_4h_mw"]
                battery_6h_mw = row["battery_6h_mw"]
                battery_8h_mw = row["battery_8h_mw"]
                battery_12h_mw = row["battery_12h_mw"]
                bess_rte = 0.86

                wind_prod, solar_prod = get_profiles(wind_cap, solar_cap, profile_file)

                results, _ = simulate_dispatch(
                    profile_file=profile_file,
                    wind_prod=wind_prod,
                    solar_prod=solar_prod,
                    baseload=baseload,
                    wind_cap=wind_cap,
                    solar_cap=solar_cap,
                    wind_price=wind_price,
                    solar_price=solar_price,
                    battery_1h_price=battery_1h_price,
                    battery_2h_price=battery_2h_price,
                    battery_4h_price=battery_4h_price,
                    battery_6h_price=battery_6h_price,
                    battery_8h_price=battery_8h_price,
                    battery_12h_price=battery_12h_price,
                    missing_energy_price=missing_energy_price,
                    battery_1h_mw=battery_1h_mw,
                    battery_2h_mw=battery_2h_mw,
                    battery_4h_mw=battery_4h_mw,
                    battery_6h_mw=battery_6h_mw,
                    battery_8h_mw=battery_8h_mw,
                    battery_12h_mw=battery_12h_mw,
                    bess_rte=0.86,
                    simulation_id=k
                )
                k += 1
                all_results.extend(results)

            result_df = pd.DataFrame(all_results)
            st.success("Batch simulation complete!")

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
            profile_file=profile_file,
            wind_prod=wind_prod,
            solar_prod=solar_prod,
            baseload=baseload,
            wind_cap=wind_cap,
            solar_cap=solar_cap,
            wind_price=wind_price,
            solar_price=solar_price,
            battery_1h_price=battery_1h_price,
            battery_2h_price=battery_2h_price,
            battery_4h_price=battery_4h_price,
            battery_6h_price=battery_6h_price,
            battery_8h_price=battery_8h_price,
            battery_12h_price=battery_12h_price,
            missing_energy_price=missing_energy_price,
            battery_1h_mw=battery_1h_mw,
            battery_2h_mw=battery_2h_mw,
            battery_4h_mw=battery_4h_mw,
            battery_6h_mw=battery_6h_mw,
            battery_8h_mw=battery_8h_mw,
            battery_12h_mw=battery_12h_mw,
            bess_rte=0.86
        )

        result_df = pd.DataFrame(results)
        st.success("✅ Simulation complete!")
        kpi_df = result_df[[
            "year",
            "Break-even 1 - Fixed Missing, EUR/MWh",
            "Break-even 2 - VWAP Missing, EUR/MWh",
            "Break-even 3 - Fixed Excess, EUR/MWh",
            "BL 1 - Fixed Missing EUR/MWh",
            "BL 2 - VWAP Missing EUR/MWh",
            "Res share in BL, %",
            "Overproduction share, %"
        ]].copy()

        kpi_df.set_index("year", inplace=True)
        average_row = kpi_df.mean()
        kpi_df.loc["Average"] = average_row

        st.subheader("Key Results")

        st.dataframe(kpi_df)

        # Define groups
        production_cols = [
            "Wind prod, MWh", "Solar prod, MWh",
            "Wind in BL, MWh", "Solar in BL, MWh"
        ]

        baseload_cols = [
            "Baseload, MWh",
            "Nr of green BL hours, h", "Nr of hours, h"
        ]

        excess_cols = [
            "Excess wind, MWh", "Excess solar, MWh",
            "Missing energy, MWh", "Cycle loss, MWh"
        ]

        price_cols = [
            "Annual avg spot, EUR/MWh",
            "Wind cap price, EUR/MWh", "PV cap price, EUR/MWh",
            "Missing energy VWAP, EUR/MWh", "Excess energy VWAP, EUR/MWh"
        ]

        battery_cycles = [
            "BESS 1h avg cycles", "BESS 2h avg cycles",
            "BESS 4h avg cycles", "BESS 6h avg cycles",
            "BESS 8h avg cycles", "BESS 12h avg cycles"
        ]

        battery_hours = [
            "BESS 1h zero hours ratio, %", "BESS 2h zero hours ratio, %",
            "BESS 4h zero hours ratio, %", "BESS 6h zero hours ratio, %",
            "BESS 8h zero hours ratio, %", "BESS 12h zero hours ratio, %",
        ]

        # Helper to extract, set index, and add average
        def format_summary_block(df, cols):
            block = df[["year"] + cols].copy()
            block.set_index("year", inplace=True)
            block.loc["Average"] = block.mean()
            return block.round(2)


        prod_df = format_summary_block(result_df, production_cols)
        base_df = format_summary_block(result_df, baseload_cols)
        excess_df = format_summary_block(result_df, excess_cols)
        vwap_df = format_summary_block(result_df, price_cols)
        battery_cycles_df = format_summary_block(result_df, battery_cycles)
        battery_hours_df = format_summary_block(result_df, battery_hours)

        # ---- 2. Display side-by-side with Streamlit columns ----

        st.subheader("Detailed Metrics by Category")

        col1, col2= st.columns(2)

        with col1:
            st.markdown("**Production & Usage**")
            st.dataframe(prod_df)

        with col2:
            st.markdown("**Baseload & Gaps**")
            st.dataframe(base_df)

        col3, col4= st.columns(2)
        with col3:
            st.markdown("**Excess / Missing**")
            st.dataframe(excess_df)

        with col4:
            st.markdown("**Price Metrics**")
            st.dataframe(vwap_df)

        col5, col6 = st.columns(2)
        with col5:
            st.markdown("**Storage Cycles Metrics**")
            st.dataframe(battery_cycles_df)
        with col6:
            st.markdown("**Storage Zero Hours Metrics**")
            st.dataframe(battery_hours_df)

        with st.expander("All Results"):
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
                yearly_df_year = yearly_df[yearly_df.index.year == year]
                year_data = summary_df[summary_df["year"] == year].set_index("price_bin")

                st.altair_chart(plot_energy_stack_st_altair(yearly_df_year, baseload_value=baseload),
                                use_container_width=True)
                year_data_reset = year_data.reset_index()

                # Missing Energy chart
                missing_chart = (
                    alt.Chart(year_data_reset)
                    .mark_bar(color="#75cfff")
                    .encode(
                        x=alt.X("price_bin:O", title="Spot Price Bin (EUR/MWh)"),
                        y=alt.Y("missing_energy:Q", title="Average Missing Energy (MWh)"),
                        tooltip=["price_bin", "missing_energy"]
                    )
                    .properties(title="Missing Energy by Price Bin", height=400)
                )

                # Excess Energy chart
                excess_chart = (
                    alt.Chart(year_data_reset)
                    .mark_bar(color="#75cfff")
                    .encode(
                        x=alt.X("price_bin:O", title="Spot Price Bin (EUR/MWh)"),
                        y=alt.Y("excess_energy:Q", title="Average Excess Energy (MWh)"),
                        tooltip=["price_bin", "excess_energy"]
                    )
                    .properties(title="Excess Energy by Price Bin", height=400)
                )

                st.altair_chart(missing_chart, use_container_width=True)
                st.altair_chart(excess_chart, use_container_width=True)