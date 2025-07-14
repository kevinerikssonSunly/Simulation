from typing import Dict, Any, List

import pandas as pd

from interfaces.StorageUnit import StorageUnit
from simulation.metrics import compile_result
from utils.calculations import vwap_energy, share_allocation


def simulate_year_dispatch(metrics: Dict[str, Any],
                           grid_connection: int,
                           year: int,
                           wind_year: pd.Series,
                           solar_year: pd.Series,
                           spot_prices: pd.DataFrame,
                           storages: List[StorageUnit],
                           baseload: float,
                           wind_cap: float,
                           solar_cap: float,
                           battery_config: Dict[int, float],
                           hydro_config: Dict[str, Any]
                           ) -> tuple[Dict, pd.DataFrame]:
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

        result, cycle_loss = simulate_hour(grid_connection, wind, solar, storages, baseload, timestamp, metrics)
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
    wind_baseload = metrics["wind_in_baseload"]
    solar_baseload = metrics["solar_in_baseload"]
    hourly_df["produced_energy"] = hourly_df["wind_total"] + hourly_df["solar_total"]

    return (
        compile_result(
            year, wind_cap, solar_cap, baseload, total_hours,
            battery_config[1], battery_config[2], battery_config[4],
            battery_config[6], battery_config[8], hydro_config["charge_mw"],
            wind_baseload, solar_baseload, wind_total, solar_total, vwap_missing, vwap_excess,vwap_wind, vwap_solar, metrics
        ),
        hourly_df
    )

def simulate_hour(
        grid_connection: int,
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
    grid_cap = grid_connection
    discharged_total = 0.0

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
        "battery_discharged": discharged_total,
        "missing_energy": missing_energy,
        "excess_energy": excess_energy,
        "wind_total": wind,
        "solar_total": solar,
    }, cycle_loss_total