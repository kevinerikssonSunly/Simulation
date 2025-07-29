import pandas as pd


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

def calculate_break_even_price_1(wind_in_baseload, wind_PaP, total_pv, pv_PaP, bess_annual_payments, excess_energy, excess_energy_vwap, missing_energy, missing_energy_price, baseload):
    baseload_price = ((wind_in_baseload * wind_PaP) + (total_pv * pv_PaP) + bess_annual_payments - (excess_energy * excess_energy_vwap) + (missing_energy * missing_energy_price)) / baseload
    return baseload_price

def calculate_break_even_price_2(total_wind, wind_PaP, total_pv, pv_PaP, bess_annual_payments, excess_energy, excess_energy_vwap, missing_energy, missing_energy_vwap, baseload):
    baseload_price = ((total_wind * wind_PaP) + (total_pv * pv_PaP) + bess_annual_payments - (excess_energy * excess_energy_vwap) + (missing_energy * missing_energy_vwap)) / baseload
    return baseload_price

def calculate_bl_price_1(wind_in_baseload, wind_PaP, solar_in_baseload, pv_PaP, bess_annual_payments, missing_energy, missing_energy_vwap, baseload):
    baseload_price = ((wind_in_baseload * wind_PaP) + (solar_in_baseload * pv_PaP) + bess_annual_payments + (missing_energy * missing_energy_vwap)) / baseload
    return baseload_price

def calculate_bl_price_2(wind_in_baseload, wind_PaP, solar_in_baseload, pv_PaP, bess_annual_payments, missing_energy, missing_energy_price, baseload):
    baseload_price = ((wind_in_baseload * wind_PaP) + (solar_in_baseload * pv_PaP) + bess_annual_payments + (missing_energy * missing_energy_price)) / baseload
    return baseload_price

def calculate_overproduction_share(excess_energy, total_wind, total_pv):
    prod_energy = total_wind + total_pv
    return round((excess_energy) / prod_energy * 100, 2)