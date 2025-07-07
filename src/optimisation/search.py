from typing import List, Dict, Any
import pandas as pd
from pandas import DataFrame
from streamlit import dataframe

from config import test
from interfaces.StorageUnit import StorageUnit
from models.storage import Storage


def simulate_dispatch_per_year(
    profile_file,
    wind_prod,
    solar_prod,
    baseload: float,
    wind_cap: float,
    solar_cap: float,
    battery_1h_mw: float,
    battery_2h_mw: float,
    battery_4h_mw: float,
    battery_6h_mw: float,
    battery_8h_mw: float,
    hydro_mw: float,
    bess_rte,
    hydro_rte,
) -> tuple[list[Any], DataFrame]:
    """
    Simulates hourly dispatch for each year based on wind and solar production profiles,
    given a fixed baseload target and battery storage configuration.

    Returns:
        List of yearly summary dictionaries.
    """
    global hourly_df
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
        "charge_mw": hydro_mw > 0,
        "volume_mwh": 2000,
    }

    df = pd.read_excel(profile_file)
    df.set_index('Hour', inplace=True)

    storages = create_storages(battery_config, hydro_config, bess_rte, hydro_rte)

    for year in years:
        wind_year = wind_prod[wind_prod.index.year == year]
        solar_year = solar_prod[solar_prod.index.year == year]
        total_hours = len(wind_year)


        metrics = {
            "produced_total": 0.0,
            "hours_met": 0,
            "redundant_wind": 0.0,
            "redundant_solar": 0.0,
            "wasted_energy": 0.0,
            "missing_energy": 0.0,
            "wind_in_baseload": 0.0,
            "solar_in_baseload": 0.0,
            "charged_wind": 0.0,
            "charged_solar": 0.0,
        }

        cycle_loss_total = 0.0
        hourly_records = []

        wind_total = wind_year.sum()
        solar_total = solar_year.sum()

        for hour in range(total_hours):
            missing_energy_this_hour = 0.0
            wasted_energy_this_hour = 0.0
            wind = round(wind_year.iloc[hour], 3)
            solar = round(solar_year.iloc[hour], 3)
            total_gen = wind + solar

            if total_gen >= baseload:
                wind_share, solar_share = baseload_allocation(wind, solar, baseload)
                metrics["wind_in_baseload"] += round(wind_share,3)
                metrics["solar_in_baseload"] += round(solar_share,3)
                metrics["produced_total"] += round(baseload)
                metrics["hours_met"] += 1

                surplus = round(total_gen, 3) - baseload

                wind_surplus, solar_surplus = allocate_surplus(wind, solar, surplus)

                charged_total = 0.0
                initial_wind_surplus = wind_surplus
                initial_solar_surplus = solar_surplus

                for storage in storages:
                    charged, redundant_wind, redundant_solar, cycle_loss = storage.charge(wind_surplus, solar_surplus)

                    cycle_loss_total += cycle_loss
                    charged_total += charged

                    wind_surplus = redundant_wind
                    solar_surplus = redundant_solar

                    if wind_surplus == 0 and solar_surplus == 0:
                        break

                metrics["charged_wind"] += initial_wind_surplus - wind_surplus
                metrics["charged_solar"] += initial_solar_surplus - solar_surplus
                metrics["redundant_wind"] += wind_surplus
                metrics["redundant_solar"] += solar_surplus
                wasted_energy_this_hour = max(surplus - charged_total, 0.0)
                metrics["wasted_energy"] += wasted_energy_this_hour

            else:
                shortfall = baseload - total_gen
                discharged_total = 0.0

                for storage in storages:
                    if shortfall <= 0:
                        break

                    discharged, cycle_loss = storage.discharge(shortfall)

                    discharged_total += discharged
                    cycle_loss_total += cycle_loss

                    shortfall -= discharged
                produced = total_gen + discharged_total
                metrics["produced_total"] += round(produced, 3)

                if produced >= baseload:
                    metrics["hours_met"] += 1
                    missing_energy_this_hour = 0.0
                else:
                    missing_energy_this_hour = baseload - produced
                    metrics["missing_energy"] += missing_energy_this_hour

            hourly_records.append({
                "timestamp": wind_year.index[hour],
                "missing_energy": missing_energy_this_hour,
                "wasted_energy": wasted_energy_this_hour,
                "Spot": df.loc[wind_year.index[hour], "Spot"]
            })

        hourly_df = pd.DataFrame(hourly_records).set_index("timestamp")

        metrics["missing_energy"] -= max(cycle_loss_total, 0)


        vwap_missing = vwap_energy(hourly_df, "missing_energy", "Spot")
        vwap_excess = vwap_energy(hourly_df, "wasted_energy", "Spot")

        export_df = hourly_df[["missing_energy", "wasted_energy", "Spot"]].copy()
        export_df.to_excel(f"test_{year}.xlsx", index=False)

        result = compile_result(
            year,
            wind_cap,
            solar_cap,
            baseload,
            total_hours,
            battery_1h_mw,
            battery_2h_mw,
            battery_4h_mw,
            battery_6h_mw,
            battery_8h_mw,
            hydro_mw,
            wind_total,
            solar_total,
            vwap_missing,
            vwap_excess,
            metrics
        )
        results_by_year.append(result)
        all_hourly_dfs.append(hourly_df)

    full_hourly_df = pd.concat(all_hourly_dfs)

    return results_by_year, full_hourly_df


def baseload_allocation(wind: float, solar: float, baseload: float) -> (float, float):
    total = wind + solar
    if total == 0:
        return 0.0, 0.0
    return (
        baseload * (wind / total),
        baseload * (solar / total)
    )

def vwap_energy(df: pd.DataFrame, energy_col: str, price_col: str) -> float:
    # Drop rows with NaNs and filter only where energy > 0
    filtered = df.dropna(subset=[energy_col, price_col])
    filtered = filtered[filtered[energy_col] > 0]

    if filtered.empty or filtered[energy_col].sum() == 0:
        return 0.0

    vwap = (filtered[energy_col] * filtered[price_col]).sum() / filtered[energy_col].sum()
    return round(vwap, 4)

def allocate_surplus(wind: float, solar: float, surplus: float) -> (float, float):
    total = wind + solar
    if total == 0:
        return 0.0, 0.0
    return (
        surplus * (wind / total),
        surplus * (solar / total)
    )
def create_storages(battery_config: Dict, hydro_config: Dict, bess_rte, hydro_rte) -> List[StorageUnit]:
    storages = []

    for duration, charge_mw in battery_config.items():
        volume = charge_mw * duration
        storages.append(Storage(charge_mw, volume, bess_rte))

    if hydro_config["enabled"]:
        storages.append(Storage(hydro_config["charge_mw"], hydro_config["volume_mwh"], hydro_rte))

    return storages


def compile_result(
    year: int,
    wind_cap: float,
    solar_cap: float,
    baseload: float,
    hours: int,
    battery_1h_mw: float,
    battery_2h_mw: float,
    battery_4h_mw: float,
    battery_6h_mw: float,
    battery_8h_mw: float,
    hydro_mw: float,
    wind_total: float,
    solar_total: float,
    vwap_missing: float,
    vwap_excess: float,
    m: Dict
) -> Dict:
    expected = baseload * hours
    return {
        "year": year,
        "wind_capacity": round(wind_cap),
        "solar_capacity": round(solar_cap),
        "BESS_1h_CHARGE_MW": battery_1h_mw,
        "BESS_2h_CHARGE_MW": battery_2h_mw,
        "BESS_4h_CHARGE_MW": battery_4h_mw,
        "BESS_6h_CHARGE_MW": battery_6h_mw,
        "BESS_8h_CHARGE_MW": battery_8h_mw,
        "pumped Hydro": hydro_mw,
        "baseload": baseload,
        "wind_total": round(wind_total),
        "solar_total": round(solar_total),
        "vwap_missing": round(vwap_missing, 6),
        "vwap_excess": round(vwap_excess, 2),
        "redundant_wind_total": round(m["redundant_wind"]),
        "redundant_solar_total": round(m["redundant_solar"]),
        "missing_energy_total": round(0 if pd.isna(m["missing_energy"]) else m["missing_energy"]),
        "green_energy_share_%": round((m["produced_total"] / expected) * 100, 2)
        if expected > 0 and pd.notna(m["produced_total"]) else 0.0,
        "actual_green_baseload_hours_%": round((m["hours_met"] / hours) * 100) if hours else 0,
        "redundant_wind_share_%": round((m["redundant_wind"] / wind_total) * 100) if wind_total else 0,
        "redundant_solar_share_%": round((m["redundant_solar"] / solar_total) * 100) if solar_total else 0,
        "excess_energy_%": round(((m["redundant_wind"] + m["redundant_solar"]) / expected) * 100) if expected else 0,
    }