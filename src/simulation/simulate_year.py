from typing import Dict, Any, List

import numpy as np
import pandas as pd

from interfaces.StorageUnit import StorageUnit
from simulation.metrics import compile_result
from utils.calculations import vwap_energy, share_allocation

def simulate_year_dispatch(
    metrics: Dict[str, Any],
    year: int,
    wind_year: pd.Series,
    solar_year: pd.Series,
    df: pd.DataFrame,
    storages: List[StorageUnit],
    baseload: float,
    is_baseload_mode: bool,
    wind_cap: float,
    solar_cap: float,
    battery_config: Dict[int, float],
) -> tuple[Dict, pd.DataFrame]:
    total_hours = len(wind_year)
    cnp_avg = np.sum(df["cnp"], axis=0) / total_hours
    wind_total = wind_year.sum()
    solar_total = solar_year.sum()

    hourly_records = []
    cycle_loss_total = 0.0

    for hour in range(total_hours):
        wind = round(wind_year.iloc[hour], 3)
        solar = round(solar_year.iloc[hour], 3)
        timestamp = wind_year.index[hour]
        spot = df.loc[timestamp, "spot"]
        cnp = df.loc[timestamp, "cnp"]

        result, cycle_loss = simulate_hour(wind, solar, storages, baseload, cnp, cnp_avg, is_baseload_mode, timestamp, metrics)
        result["timestamp"] = timestamp
        result["Spot"] = spot

        hourly_records.append(result)
        cycle_loss_total += cycle_loss

    metrics["cycle_loss_total"] = cycle_loss_total
    metrics["missing_energy"] = max(0, metrics["missing_energy"] - cycle_loss_total)

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
            battery_config[6], battery_config[8], battery_config[12],
            wind_baseload, solar_baseload, wind_total, solar_total, vwap_missing, vwap_excess, vwap_wind, vwap_solar, metrics
        ),
        hourly_df
    )

def sequential_bess_charging(storages, wind_surplus, solar_surplus):
    """
    Charges storages in sequential order: each BESS gets up to its MW limit for the hour,
    as long as it has room. Keeps going until surplus runs out or all BESS are full.
    Returns:
      - remaining_wind (float)
      - remaining_solar (float)
      - total_cycle_loss (float)
      - total_charged (float)
    """
    remaining_wind = max(0.0, wind_surplus)
    remaining_solar = max(0.0, solar_surplus)
    total_cycle_loss = 0.0
    total_charged = 0.0

    for storage in storages:
        soc_headroom = max(0.0, storage.max_volume - storage.soc)
        if soc_headroom < 1e-6:
            continue

        slice_mwh = min(storage.max_charge, soc_headroom, remaining_wind + remaining_solar)
        if slice_mwh < 1e-6:
            continue

        total_surplus = remaining_wind + remaining_solar
        wind_frac = remaining_wind / total_surplus if total_surplus > 0 else 0.0
        solar_frac = 1.0 - wind_frac

        slice_wind = slice_mwh * wind_frac
        slice_solar = slice_mwh * solar_frac

        charged, leftover_wind, leftover_solar, loss = storage.charge(slice_wind, slice_solar)

        actual_charged_wind = slice_wind - leftover_wind
        actual_charged_solar = slice_solar - leftover_solar

        remaining_wind = max(0.0, remaining_wind - actual_charged_wind)
        remaining_solar = max(0.0, remaining_solar - actual_charged_solar)

        total_charged += actual_charged_wind + actual_charged_solar
        total_cycle_loss += max(0.0, loss)

        if remaining_wind + remaining_solar < 1e-6:
            break

    return remaining_wind, remaining_solar, total_cycle_loss, total_charged

def simulate_hour(
    wind: float,
    solar: float,
    storages: List[StorageUnit],
    baseload: float,
    cnp: float,
    cnp_avg: float,
    is_baseload_mode: bool,
    timestamp: pd.Timestamp,
    metrics: Dict
) -> tuple[Dict[str, float], float]:

    total_gen = wind + solar
    missing_energy = 0.0
    excess_energy = 0.0
    cycle_loss_total = 0.0
    discharged_total = 0.0
    charged_total = 0.0

    if not is_baseload_mode:
        baseload *= cnp / cnp_avg

    if total_gen >= baseload:
        wind_in_baseload, solar_in_baseload = share_allocation(wind, solar, baseload)

        metrics["wind_in_baseload"] += wind_in_baseload
        metrics["solar_in_baseload"] += solar_in_baseload
        metrics["produced_total"] += baseload
        metrics["hours_met"] += 1

        surplus = total_gen - baseload
        wind_surplus, solar_surplus = share_allocation(wind, solar, surplus)
        initial_wind_surplus, initial_solar_surplus = wind_surplus, solar_surplus

        wind_surplus, solar_surplus, loss, charged = sequential_bess_charging(
            storages, wind_surplus, solar_surplus
        )
        cycle_loss_total += loss
        charged_total += charged

        bess_remaining_wind = wind_surplus
        bess_remaining_solar = solar_surplus
        remaining_surplus = bess_remaining_wind + bess_remaining_solar

        to_grid_wind, to_grid_solar = share_allocation(bess_remaining_wind, bess_remaining_solar, remaining_surplus)
        metrics["excess_wind"] += to_grid_wind
        metrics["excess_solar"] += to_grid_solar

        redundant_wind = bess_remaining_wind - to_grid_wind
        redundant_solar = bess_remaining_solar - to_grid_solar
        metrics["redundant_wind"] += redundant_wind
        metrics["redundant_solar"] += redundant_solar

        metrics["charged_wind"] += initial_wind_surplus - bess_remaining_wind
        metrics["charged_solar"] += initial_solar_surplus - bess_remaining_solar

        metrics["excess_energy"] += remaining_surplus
        excess_energy = remaining_surplus

    else:
        shortfall = baseload - total_gen

        metrics["wind_in_baseload"] += wind
        metrics["solar_in_baseload"] += solar
        wind_discharged = 0
        solar_discharged = 0
        for storage in storages:
            if shortfall <= 0:
                break
            discharged, wind_discharged, solar_discharged, loss = storage.discharge(shortfall, timestamp)
            discharged_total += discharged
            cycle_loss_total += loss
            shortfall -= discharged


        produced = total_gen + discharged_total
        metrics["produced_total"] += produced
        metrics["wind_in_baseload"] += wind_discharged
        metrics["solar_in_baseload"] += solar_discharged

        if produced >= baseload:
            metrics["hours_met"] += 1
        else:
            missing_energy = baseload - produced
            metrics["missing_energy"] += missing_energy

    return {
        "battery_discharged": discharged_total,
        "battery_charged": charged_total,
        "missing_energy": missing_energy,
        "excess_energy": excess_energy,
        "wind_total": wind,
        "solar_total": solar,
        "baseload": baseload
    }, cycle_loss_total