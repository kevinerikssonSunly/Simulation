from typing import List, Dict, Any
import pandas as pd
from pandas import DataFrame

from constraints import GRID_CONNECTION
from interfaces.StorageUnit import StorageUnit
from models.storage import Storage

def calculate_BL_price(total_wind, wind_PaP, total_pv, pv_PaP, bess_annual_payments, excess_energy, excess_energy_vwap, missing_energy, missing_energy_price, baseload):
    baseload_price = ((total_wind * wind_PaP) + (total_pv * pv_PaP) + bess_annual_payments - (excess_energy * excess_energy_vwap) + (missing_energy * missing_energy_price)) / baseload
    return baseload_price

def calculate_break_even_price(total_wind, wind_PaP, total_pv, pv_PaP, bess_annual_payments, excess_energy, excess_energy_vwap, missing_energy, missing_energy_vwap, baseload):
    baseload_price = ((total_wind * wind_PaP) + (total_pv * pv_PaP) + bess_annual_payments - (excess_energy * excess_energy_vwap) + (missing_energy * missing_energy_vwap)) / baseload
    return baseload_price

def simulate_dispatch_per_year(
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

        metrics = {
            "produced_total": 0.0,
            "hours_met": 0,
            "excess_wind": 0.0,
            "excess_solar": 0.0,
            "redundant_wind": 0.0,
            "redundant_solar": 0.0,
            "excess_energy": 0.0,
            "missing_energy": 0.0,
            "wind_in_baseload": 0.0,
            "solar_in_baseload": 0.0,
            "charged_wind": 0.0,
            "charged_solar": 0.0,
            "discharged": 0.0,
            "cycle_loss": 0.0,
            "wind_price": wind_price,
            "solar_price": solar_price,
            "battery_1h_price": battery_1h_price,
            "battery_2h_price": battery_2h_price,
            "battery_4h_price": battery_4h_price,
            "battery_6h_price": battery_6h_price,
            "battery_8h_price": battery_8h_price,
            "hydro_storage_price": hydro_storage_price,
            "missing_energy_price": missing_energy_price,
        }

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
        baseload_price = calculate_BL_price(wind_prod_year.sum(), wind_price, solar_prod_year.sum(), solar_price, total_storage_cost, excess_energy, result["Excess energy VWAP, EUR/MWh"], result["Missing energy, MWh"], missing_energy_price, baseload * len(wind_prod_year))
        baseload_break_even_price = calculate_BL_price(wind_prod_year.sum(), wind_price, solar_prod_year.sum(), solar_price, total_storage_cost, excess_energy, result["Excess energy VWAP, EUR/MWh"], result["Missing energy, MWh"], result["Missing energy VWAP, EUR/MWh"], baseload * len(wind_prod_year))
        result["BL price, EUR/MWh"] = round(baseload_price, 2)
        result["BL break-even, EUR/MWh"] = round(baseload_break_even_price, 2)
        result["Annual avg sport, EUR/MWh"] = hourly_df["Spot"].mean()

        results_by_year.append(result)
        all_hourly_dfs.append(hourly_df)

        for i, storage in enumerate(storages[:-1] if hydro_config["enabled"] else storages):
            yearly_cycles = storage.get_average_cycles_per_year()
            avg_daily_cycles = yearly_cycles / (len(wind_prod_year) / 24)
            result[f"{storage.name} avg cycles"] = round(avg_daily_cycles, 2)

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

        result, cycle_loss = simulate_hour(wind, solar, storages, baseload, timestamp, metrics)
        result["timestamp"] = timestamp
        result["Spot"] = spot

        hourly_records.append(result)
        cycle_loss_total += cycle_loss


    metrics["cycle_loss_total"] = cycle_loss_total
    metrics["missing_energy"] -= cycle_loss_total

    hourly_df = pd.DataFrame(hourly_records).set_index("timestamp")
    vwap_missing = vwap_energy(hourly_df, "missing_energy", "Spot")
    vwap_excess = vwap_energy(hourly_df, "excess_energy", "Spot")
    vwap_wind = vwap_energy(hourly_df, "wind_total", "Spot")
    vwap_solar = vwap_energy(hourly_df, "solar_total", "Spot")


    return (
        compile_result(
            year, wind_cap, solar_cap, baseload, total_hours,
            battery_config[1], battery_config[2], battery_config[4],
            battery_config[6], battery_config[8], hydro_config["charge_mw"],
            wind_total, solar_total, vwap_missing, vwap_excess,vwap_wind, vwap_solar, metrics
        ),
        hourly_df
    )

def simulate_hour(
        wind: float,
        solar: float,
        storages: List[StorageUnit],
        baseload: float,
        timestamp: pd.Timestamp,
        metrics: Dict
) -> tuple[Dict[str, float], float]:

    total_gen = wind + solar
    missing_energy = excess_energy = 0.0
    cycle_loss_total = 0.0
    grid_cap = GRID_CONNECTION

    if total_gen >= baseload:
        wind_in_baseload, solar_in_baseload = share_allocation(wind, solar, baseload)

        metrics["wind_in_baseload"] += wind_in_baseload
        metrics["solar_in_baseload"] += solar_in_baseload
        metrics["produced_total"] += baseload
        metrics["hours_met"] += 1

        surplus = total_gen - baseload
        wind_surplus, solar_surplus = share_allocation(wind, solar, surplus)
        initial_wind_surplus, initial_solar_surplus = wind_surplus, solar_surplus

        for storage in storages:
            charged, wind_surplus, solar_surplus, loss = storage.charge(wind_surplus, solar_surplus)
            cycle_loss_total += loss
            if wind_surplus == 0 and solar_surplus == 0:
                break

        bess_remaining_wind = wind_surplus
        bess_remaining_solar = solar_surplus
        remaining_surplus = bess_remaining_wind + bess_remaining_solar

        available_grid_surplus = max(grid_cap - baseload, 0.0)
        to_grid_total = min(remaining_surplus, available_grid_surplus)

        to_grid_wind, to_grid_solar = share_allocation(bess_remaining_wind, bess_remaining_solar, to_grid_total)
        metrics["excess_wind"] += to_grid_wind
        metrics["excess_solar"] += to_grid_solar

        redundant_wind = bess_remaining_wind - to_grid_wind
        redundant_solar = bess_remaining_solar - to_grid_solar
        metrics["redundant_wind"] += redundant_wind
        metrics["redundant_solar"] += redundant_solar

        metrics["charged_wind"] += initial_wind_surplus - bess_remaining_wind
        metrics["charged_solar"] += initial_solar_surplus - bess_remaining_solar

        metrics["excess_energy"] += to_grid_total
        excess_energy = to_grid_total

    else:
        shortfall = baseload - total_gen
        discharged_total = 0.0

        for storage in storages:
            if shortfall <= 0:
                break
            discharged, loss = storage.discharge(shortfall, timestamp)
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
        "excess_energy": excess_energy,
        "wind_total": wind,
        "solar_total": solar,
    }, cycle_loss_total


def vwap_energy(df: pd.DataFrame, energy_col: str, price_col: str) -> float:
    filtered = df.dropna(subset=[energy_col, price_col])
    filtered = filtered[filtered[energy_col] > 0]

    if filtered.empty or filtered[energy_col].sum() == 0:
        return 0.0

    vwap = (filtered[energy_col] * filtered[price_col]).sum() / filtered[energy_col].sum()
    return round(vwap, 4)

def share_allocation(wind: float, solar: float, surplus: float) -> (float, float):
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
        storages.append(Storage(charge_mw, volume, bess_rte, name=f"BESS {duration}h"))

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
    vwap_wind: float,
    vwap_solar: float,
    m: Dict
) -> Dict:
    expected_baseload = baseload * hours
    return {
        "year": year,
        "BL price, EUR/MWh": "",
        "BL break-even, EUR/MWh": "",
        "Annual avg spot, EUR/MWh": "",
        "Res share in BL, %": round((m["produced_total"] / expected_baseload) * 100, 2) if expected_baseload > 0 and pd.notna(
            m["produced_total"]) else 0.0,
        "Nr of green BL hours, h": m["hours_met"],
        "Nr of hours, h": hours,
        "Wind cap price, EUR/MWh": round(vwap_wind, 2),
        "PV cap price, EUR/MWh": round(vwap_solar, 2),
        "Missing energy VWAP, EUR/MWh": round(vwap_missing, 2),
        "Excess energy VWAP, EUR/MWh": round(vwap_excess, 2),
        "Baseload, MWh": expected_baseload,
        "Missing energy, MWh": round(0 if pd.isna(m["missing_energy"]) else m["missing_energy"]),
        "Cycle loss, MWh": round(m["cycle_loss_total"], 2),
        "Solar prod, MWh": round(solar_total),
        "Wind prod, MWh": round(wind_total),
        "Excess wind, MWh": round(m["excess_wind"]),
        "Excess solar, MWh": round(m["excess_solar"]),
        "Redundant wind, MWh": round(m["redundant_wind"]),
        "Redundant solar, MWh": round(m["redundant_solar"]),
        "BESS 1h avg cycles": "",
        "BESS 2h avg cycles": "",
        "BESS 4h avg cycles": "",
        "BESS 6h avg cycles": "",
        "BESS 8h avg cycles": "",


        "wind_capacity": round(wind_cap),
        "solar_capacity": round(solar_cap),
        "BESS_1h_CHARGE_MW": battery_1h_mw,
        "BESS_2h_CHARGE_MW": battery_2h_mw,
        "BESS_4h_CHARGE_MW": battery_4h_mw,
        "BESS_6h_CHARGE_MW": battery_6h_mw,
        "BESS_8h_CHARGE_MW": battery_8h_mw,
        "pumped Hydro": hydro_mw,
        "Baseload, MW": baseload,
        "Wind PaP price, EUR/MWh": m["wind_price"],
        "PV PaP price, EUR/MWh": m["solar_price"],
        "BESS 1h annual payment, EUR/MWh": m["battery_1h_price"],
        "BESS 2h annual payment, EUR/MWh": m["battery_2h_price"],
        "BESS 4h annual payment, EUR/MWh": m["battery_4h_price"],
        "BESS 6h annual payment, EUR/MWh": m["battery_6h_price"],
        "BESS 8h annual payment, EUR/MWh": m["battery_8h_price"],
        "Pumped Hydro annual payment, EUR/MWh": m["hydro_storage_price"],
        "Missing energy price, EUR/MWh": m["missing_energy_price"],
    }