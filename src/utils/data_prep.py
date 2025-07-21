from pathlib import Path

import pandas as pd

from config import YIELD_LV, PV_WIND_PROD_LV, PV_WIND_PROD_LT, YIELD_LT, PV_WIND_PROD_PL, YIELD_PL


def load_profiles(data_hourly, data_yearly
) -> pd.DataFrame:
    """
    Loads and normalizes hourly wind and solar production profiles for each year using annual production data.

    Args:
        data_hourly: Path to the Excel file containing hourly raw production data.
        data_yearly: Path to the Excel file containing annual production per MW of installed capacity.

    Returns:
        A DataFrame indexed by datetime with columns: 'Year', 'wind_profile', 'solar_profile'.
    """
    df_hourly = pd.read_excel(data_hourly).ffill()
    df_yearly = pd.read_excel(data_yearly).ffill()

    df_hourly['Hour'] = pd.to_datetime(df_hourly['Hour'])
    df_hourly['Year'] = df_hourly['Hour'].dt.year

    df_hourly['wind_profile'] = 0.0
    df_hourly['solar_profile'] = 0.0

    for year in df_yearly['Year'].unique():
        mask = df_hourly['Year'] == year

        wind_hourly = df_hourly.loc[mask, 'Wind']
        solar_hourly = df_hourly.loc[mask, 'Solar']

        wind_annual = df_yearly.loc[df_yearly['Year'] == year, 'WIND - Annual prod MWh, MW'].values[0]
        solar_annual = df_yearly.loc[df_yearly['Year'] == year, 'SOLAR - Annual prod MWh, MW'].values[0]

        df_hourly.loc[mask, 'wind_profile'] = wind_hourly / (wind_hourly.sum() / wind_annual)
        df_hourly.loc[mask, 'solar_profile'] = solar_hourly / (solar_hourly.sum() / solar_annual)

    df_hourly[['Hour', 'Year', 'wind_profile', 'solar_profile']].to_excel('/Users/kevineriksson/PycharmProjects/Simulation/data/profiles_LV.xlsx', index=False)
    return df_hourly[['Year', 'wind_profile', 'solar_profile']]

def extract_from_file(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    df.dropna(how='all', inplace=True)
    return df




