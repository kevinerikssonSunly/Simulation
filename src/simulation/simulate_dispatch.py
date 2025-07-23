from typing import Any

import pandas as pd
from pandas import DataFrame

from simulation.metrics import init_metrics
from simulation.simulate_year import simulate_year_dispatch
from simulation.storage_factory import create_storages
from utils.calculations import calculate_break_even_price_1, calculate_break_even_price_2, \
    calculate_bl_price_1, calculate_bl_price_2, calculate_overproduction_share

def simulate_dispatch(
    profile_file,
    wind_prod,
    solar_prod,
    baseload: float,
    wind_cap: float,
    solar_cap: float,
    wind_price: float,
    solar_price: float,
    battery_1h_price: float,
    battery_2h_price: float,
    battery_4h_price: float,
    battery_6h_price: float,
    battery_8h_price: float,
    hydro_storage_price: float,
    missing_energy_price: float,
    wind_excess_energy_price: float,
    solar_excess_energy_price: float,
    battery_1h_mw: float,
    battery_2h_mw: float,
    battery_4h_mw: float,
    battery_6h_mw: float,
    battery_8h_mw: float,
    hydro_mw: float,
    bess_rte,
    hydro_rte,
    simulation_id: int = 1,
) -> tuple[list[Any], DataFrame]:
    results_by_year = []
    all_hourly_dfs = []
    years = wind_prod.index.year.unique()

    battery_config = {
        1: battery_1h_mw,
        2: battery_2h_mw,
        4: battery_4h_mw,
        6: battery_6h_mw,
        8: battery_8h_mw,
    }
    hydro_config = {
        "enabled": hydro_mw > 0,
        "charge_mw": hydro_mw,
        "volume_mwh": 2000,
    }

    df = pd.read_excel(profile_file)
    df.set_index('Hour', inplace=True)

    storages = create_storages(battery_config, hydro_config, bess_rte, hydro_rte)

    for year in years:
        wind_prod_year = wind_prod[wind_prod.index.year == year]
        solar_prod_year = solar_prod[solar_prod.index.year == year]

        metrics = init_metrics(wind_price, solar_price, battery_1h_price, battery_2h_price, battery_4h_price, battery_6h_price, battery_8h_price, hydro_storage_price, missing_energy_price)

        result, hourly_df = simulate_year_dispatch(metrics, year, wind_prod_year, solar_prod_year, df,
                                                       storages, baseload, wind_cap, solar_cap, battery_config, hydro_config)

        total_storage_cost = sum([
            battery_1h_price,
            battery_2h_price,
            battery_4h_price,
            battery_6h_price,
            battery_8h_price,
            hydro_storage_price
        ])

        excess_energy = result["Excess wind, MWh"] + result["Excess solar, MWh"]
        redundant_energy = result["Redundant wind, MWh"] + result["Redundant solar, MWh"]
        bl_price_1 = calculate_bl_price_1(result["Wind in BL, MWh"], wind_price, result["Solar in BL, MWh"], solar_price, total_storage_cost, result["Missing energy, MWh"], missing_energy_price, baseload * len(wind_prod_year) )
        bl_price_2 = calculate_bl_price_2(result["Wind in BL, MWh"], wind_price, result["Solar in BL, MWh"], solar_price, total_storage_cost, result["Missing energy, MWh"], result["Missing energy VWAP, EUR/MWh"], baseload * len(wind_prod_year) )

        brake_even_1 = calculate_break_even_price_1(wind_prod_year.sum(), wind_price, solar_prod_year.sum(), solar_price, total_storage_cost, result["Excess wind, MWh"], wind_excess_energy_price, result["Excess solar, MWh"], solar_excess_energy_price, result["Missing energy, MWh"], missing_energy_price, baseload * len(wind_prod_year))
        brake_even_2 = calculate_break_even_price_2(wind_prod_year.sum(), wind_price, solar_prod_year.sum(), solar_price, total_storage_cost, result["Excess wind, MWh"], wind_excess_energy_price, result["Excess solar, MWh"], solar_excess_energy_price, result["Missing energy, MWh"], result["Missing energy VWAP, EUR/MWh"], baseload * len(wind_prod_year))
        result["BL 1, EUR/MWh"] = round(bl_price_1, 2)
        result["BL 2, EUR/MWh"] = round(bl_price_2, 2)
        result["Break-even - Fixed Missing, EUR/MWh"] = round(brake_even_1, 2)
        result["Break-even - VWAP Missing, EUR/MWh"] = round(brake_even_2, 2)
        result["Annual avg spot, EUR/MWh"] = hourly_df["Spot"].mean()
        result["Overproduction share, %"] = calculate_overproduction_share(excess_energy, redundant_energy, wind_prod_year.sum(), solar_prod_year.sum())
        result["Simulation id"] = simulation_id

        results_by_year.append(result)
        all_hourly_dfs.append(hourly_df)

        for i, storage in enumerate(storages[:-1] if hydro_config["enabled"] else storages):
            yearly_cycles = storage.get_average_cycles_per_year()
            avg_daily_cycles = yearly_cycles / (len(wind_prod_year) / 24)
            result[f"{storage.name} avg cycles"] = round(avg_daily_cycles, 2)
            result[f"{storage.name} zero hours"] = round(storage.get_zero_hours() / len(wind_prod_year) * 100, 2)
            storage.reset_yearly_energy()
            storage.reset_yearly_zero_hours()

    full_hourly_df = pd.concat(all_hourly_dfs)

    return results_by_year, full_hourly_df