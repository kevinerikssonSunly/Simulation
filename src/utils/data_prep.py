import pandas as pd
from config import DATA_YEARLY, DATA_HOURLY

def load_profiles(data_hourly, data_yearly):
    df_hourly = pd.read_excel(data_hourly)
    df_yearly = pd.read_excel(data_yearly)
    df_hourly = df_hourly.ffill()
    df_yearly = df_yearly.ffill()

    df_hourly['Hour'] = pd.to_datetime(df_hourly['Hour'])
    df_hourly['Year'] = df_hourly['Hour'].dt.year

    df_hourly['wind_profile'] = 0.0
    df_hourly['solar_profile'] = 0.0

    years = df_yearly['Year'].unique()

    for year in years:
        mask = df_hourly['Year'] == year
        wind_hourly = df_hourly.loc[mask, 'PROEEWINDON_ENTSOE']
        solar_hourly = df_hourly.loc[mask, 'PROEESOL_ENTSOE']

        wind_yearly = df_yearly.loc[df_yearly['Year'] == year, 'WIND - Annual prod MWh, MW'].values[0]
        solar_yearly = df_yearly.loc[df_yearly['Year'] == year, 'SOLAR - Annual prod MWh, MW'].values[0]

        df_hourly.loc[mask, 'wind_profile'] = wind_hourly / (wind_hourly.sum() / wind_yearly)
        df_hourly.loc[mask, 'solar_profile'] = solar_hourly / (solar_hourly.sum() / solar_yearly)
    df_hourly.set_index('Hour', inplace=True)
    return df_hourly[['Year', 'wind_profile', 'solar_profile']]
