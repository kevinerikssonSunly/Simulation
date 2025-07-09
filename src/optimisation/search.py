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
        wind_prod_year = wind_prod[wind_prod.index.year == year]
        solar_prod_year = solar_prod[solar_prod.index.year == year]
        spot_price_year = df.loc[df.index.year == year, "Spot"]

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

        result, hourly_df = simulate_year_dispatch(metrics, year, wind_prod_year, solar_prod_year, df,
                                                       storages, baseload, wind_cap, solar_cap, battery_config, hydro_config)

        results_by_year.append(result)
        all_hourly_dfs.append(hourly_df)

    full_hourly_df = pd.concat(all_hourly_dfs)

    return results_by_year, full_hourly_df

def simulate_year_dispatch(metrics: Dict[str, Any],
                           year: int,
                           wind_year: pd.Series,
                           solar_year: pd.Series,
                           spot_prices: pd.DataFrame,
                           storages: List[StorageUnit],
                           baseload: float,
                           wind_cap: float,
                           solar_cap: float,
                           battery_config: Dict[int, float],
                           hydro_config: Dict[str, Any]) -> tuple[Dict, pd.DataFrame]:
    total_hours = len(wind_year)
    wind_total = wind_year.sum()
    solar_total = solar_year.sum()

    hourly_records = []
    cycle_loss_total = 0.0

    for hour in range(total_hours):
        wind = round(wind_year.iloc[hour], 3)
        solar = round(solar_year.iloc[hour], 3)
        timestamp = wind_year.index[hour]
        spot = spot_prices.loc[timestamp, "Spot"]

        result, cycle_loss = simulate_hour(wind, solar, storages, baseload, metrics)
        result["timestamp"] = timestamp
        result["Spot"] = spot

        hourly_records.append(result)
        cycle_loss_total += cycle_loss

    metrics["missing_energy"] -= max(cycle_loss_total, 0)

    hourly_df = pd.DataFrame(hourly_records).set_index("timestamp")
    vwap_missing = vwap_energy(hourly_df, "missing_energy", "Spot")
    vwap_excess = vwap_energy(hourly_df, "wasted_energy", "Spot")

    return (
        compile_result(
            year, wind_cap, solar_cap, baseload, total_hours,
            battery_config[1], battery_config[2], battery_config[4],
            battery_config[6], battery_config[8], hydro_config["charge_mw"],
            wind_total, solar_total, vwap_missing, vwap_excess, metrics
        ),
        hourly_df
    )

def simulate_hour(
        wind: float,
        solar: float,
        storages: List[StorageUnit],
        baseload: float,
        metrics: Dict
) -> tuple[Dict[str, float], float]:

    total_gen = wind + solar
    missing_energy = wasted_energy = 0.0
    cycle_loss_total = 0.0

    if total_gen >= baseload:
        wind_share, solar_share = baseload_allocation(wind, solar, baseload)
        surplus = total_gen - baseload

        metrics["wind_in_baseload"] += wind_share
        metrics["solar_in_baseload"] += solar_share
        metrics["produced_total"] += baseload
        metrics["hours_met"] += 1

        wind_surplus, solar_surplus = allocate_surplus(wind, solar, surplus)
        initial_wind_surplus, initial_solar_surplus = wind_surplus, solar_surplus
        charged_total = 0.0

        for storage in storages:
            charged, wind_surplus, solar_surplus, loss = storage.charge(wind_surplus, solar_surplus)
            charged_total += charged
            cycle_loss_total += loss
            if wind_surplus == 0 and solar_surplus == 0:
                break

        metrics["charged_wind"] += initial_wind_surplus - wind_surplus
        metrics["charged_solar"] += initial_solar_surplus - solar_surplus
        metrics["redundant_wind"] += wind_surplus
        metrics["redundant_solar"] += solar_surplus
        wasted_energy = max(surplus - charged_total, 0.0)
        metrics["wasted_energy"] += wasted_energy

    else:
        shortfall = baseload - total_gen
        discharged_total = 0.0

        for storage in storages:
            if shortfall <= 0:
                break
            discharged, loss = storage.discharge(shortfall)
            discharged_total += discharged
            cycle_loss_total += loss
            shortfall -= discharged

        produced = total_gen + discharged_total
        metrics["produced_total"] += produced

        if produced >= baseload:
            metrics["hours_met"] += 1
        else:
            missing_energy = baseload - produced
            metrics["missing_energy"] += missing_energy

    return {
        "missing_energy": missing_energy,
        "wasted_energy": wasted_energy
    }, cycle_loss_total

def baseload_allocation(wind: float, solar: float, baseload: float) -> (float, float):
    total = wind + solar
    if total == 0:
        return 0.0, 0.0
    return (
        baseload * (wind / total),
        baseload * (solar / total)
    )

def vwap_energy(df: pd.DataFrame, energy_col: str, price_col: str) -> float:
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
        "BL price, EUR/MWh": "",
        "BL break-even, EUR/MWh": "",
        "Annual avg sport, EUR/MWh": "",
        "Missing energy VWAP, EUR/MWh": round(vwap_missing, 6),
        "Excess energy VWAP, EUR/MWh": round(vwap_excess, 2),
        "redundant_wind_total": round(m["redundant_wind"]),
        "redundant_solar_total": round(m["redundant_solar"]),
        "Missing energy, MWh": round(0 if pd.isna(m["missing_energy"]) else m["missing_energy"]),
        "Wind prod, MWh": round(wind_total),
        "Solar prod, MWh": round(solar_total),
        "Res share in BL, %": round((m["produced_total"] / expected) * 100, 2) if expected > 0 and pd.notna(m["produced_total"]) else 0.0,
        "Nr of green BL hours, h": round((m["hours_met"] / hours) * 100) if hours else 0,
        "Wind cap price, EUR/MWh": "",
        "PV cap price, EUR/MWh": "",
        "Baseload, MWh": baseload,
        "excess_energy_%": round(((m["redundant_wind"] + m["redundant_solar"]) / expected) * 100) if expected else 0,
        "wind_capacity": round(wind_cap),
        "solar_capacity": round(solar_cap),
        "BESS_1h_CHARGE_MW": battery_1h_mw,
        "BESS_2h_CHARGE_MW": battery_2h_mw,
        "BESS_4h_CHARGE_MW": battery_4h_mw,
        "BESS_6h_CHARGE_MW": battery_6h_mw,
        "BESS_8h_CHARGE_MW": battery_8h_mw,
        "pumped Hydro": hydro_mw,
    }