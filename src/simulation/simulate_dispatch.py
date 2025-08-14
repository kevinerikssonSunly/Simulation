from typing import Any

import pandas as pd
from pandas import DataFrame

from simulation.metrics import init_metrics
from simulation.simulate_year import simulate_year_dispatch
from simulation.storage_factory import create_storages
from utils.calculations import calculate_break_even_price_1, calculate_break_even_price_2, \
    calculate_bl_price_1, calculate_bl_price_2, calculate_overproduction_share, calculate_break_even_price_3


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
    battery_12h_price: float,
    missing_energy_price: float,
    battery_1h_mw: float,
    battery_2h_mw: float,
    battery_4h_mw: float,
    battery_6h_mw: float,
    battery_8h_mw: float,
    battery_12h_mw: float,
    bess_rte,
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
        12: battery_12h_mw,
    }

    df = pd.read_excel(profile_file)
    df.set_index('Hour', inplace=True)

    storages = create_storages(battery_config, bess_rte)

    for year in years:
        wind_prod_year = wind_prod[wind_prod.index.year == year]
        solar_prod_year = solar_prod[solar_prod.index.year == year]

        metrics = init_metrics(wind_price, solar_price, battery_1h_price, battery_2h_price, battery_4h_price, battery_6h_price, battery_8h_price, battery_12h_price, missing_energy_price)

        result, hourly_df = simulate_year_dispatch(metrics, year, wind_prod_year, solar_prod_year, df,
                                                       storages, baseload, wind_cap, solar_cap, battery_config)

        total_storage_cost = sum([
            battery_1h_price,
            battery_2h_price,
            battery_4h_price,
            battery_6h_price,
            battery_8h_price,
            battery_12h_price
        ])

        excess_energy = result["Excess wind, MWh"] + result["Excess solar, MWh"]
        #redundant_energy = result["Redundant wind, MWh"] + result["Redundant solar, MWh"]
        bl_price_1 = calculate_bl_price_1(result["Wind in BL, MWh"], wind_price, result["Solar in BL, MWh"],
                                          solar_price, total_storage_cost, result["Missing energy, MWh"],
                                          missing_energy_price, baseload * len(wind_prod_year))
        bl_price_2 = calculate_bl_price_2(result["Wind in BL, MWh"], wind_price, result["Solar in BL, MWh"],
                                          solar_price, total_storage_cost, result["Missing energy, MWh"],
                                          result["Missing energy VWAP, EUR/MWh"], baseload * len(wind_prod_year))

        brake_even_1 = calculate_break_even_price_1(
                wind_prod_year.sum(), wind_price,
                solar_prod_year.sum(), solar_price,
                total_storage_cost, excess_energy,
                result["Excess energy VWAP, EUR/MWh"],
                result["Missing energy, MWh"], missing_energy_price,
                baseload * len(wind_prod_year)
            )

        brake_even_2 = calculate_break_even_price_2(
            wind_prod_year.sum(), wind_price,
            solar_prod_year.sum(), solar_price,
            total_storage_cost, excess_energy,
            result["Excess energy VWAP, EUR/MWh"],
            result["Missing energy, MWh"],
            result["Missing energy VWAP, EUR/MWh"],
            baseload * len(wind_prod_year)
        )

        brake_even_3 = calculate_break_even_price_3(
            wind_prod_year.sum(), wind_price,
            solar_prod_year.sum(), solar_price,
            total_storage_cost, excess_energy,
            result["Missing energy, MWh"], missing_energy_price,
            baseload * len(wind_prod_year)
        )

        result["BL 1 - Fixed Missing EUR/MWh"] = round(bl_price_1)
        result["BL 2 - VWAP Missing EUR/MWh"] = round(bl_price_2)
        result["Break-even 1 - Fixed Missing, EUR/MWh"] = round(brake_even_1)
        result["Break-even 2 - VWAP Missing, EUR/MWh"] = round(brake_even_2)
        result["Break-even 3 - Excess En. Price Fixed 0, EUR/MWh"] = round(brake_even_3)
        result["Annual avg spot, EUR/MWh"] = round(hourly_df["Spot"].mean())
        result["Overproduction share, %"] = round(calculate_overproduction_share(excess_energy, wind_prod_year.sum(), solar_prod_year.sum()))
        result["Simulation id"] = simulation_id

        results_by_year.append(result)
        all_hourly_dfs.append(hourly_df)

        total_hours = len(wind_prod_year)
        hours_per_day = 24

        for storage_name in ["BESS 1h", "BESS 2h", "BESS 4h", "BESS 6h", "BESS 8h", "BESS 12h"]:
            storage = next((s for s in storages if s.name == storage_name), None)

            # If this BESS wasn't instantiated (or has no power), report as unused: 0 cycles, 100% zero-hours
            if storage is None or getattr(storage, "max_charge", 0) <= 0:
                result[f"{storage_name} avg cycles"] = 0.0
                result[f"{storage_name} zero hours ratio, %"] = 100.0
                continue

            # Determine if it actually did any work this year
            yearly_energy = getattr(storage, "get_yearly_energy", lambda: 0.0)()
            yearly_cycles = storage.get_average_cycles_per_year()

            if (yearly_energy or 0.0) <= 0 and (yearly_cycles or 0.0) <= 0:
                # existed but never used
                result[f"{storage_name} avg cycles"] = 0.0
                result[f"{storage_name} zero hours ratio, %"] = 100.0
            else:
                avg_daily_cycles = yearly_cycles / (total_hours / hours_per_day)
                zero_hours_ratio = (storage.get_zero_hours() / total_hours) * 100
                result[f"{storage_name} avg cycles"] = round(avg_daily_cycles, 2)
                result[f"{storage_name} zero hours ratio, %"] = round(zero_hours_ratio)

        # Only reset after reading metrics
        for s in storages:
            if hasattr(s, "reset_yearly_energy"): s.reset_yearly_energy()
            if hasattr(s, "reset_yearly_zero_hours"): s.reset_yearly_zero_hours()

    full_hourly_df = pd.concat(all_hourly_dfs)

    return results_by_year, full_hourly_df