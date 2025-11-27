import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def plot_energy_stack_st_altair(df, baseload_value):
    df_plot = df.copy()

    df_plot = df_plot[["produced_energy", "battery_discharged", "battery_charged"]].fillna(0)
    df_plot["baseload"] = df_plot["Consumption"]

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