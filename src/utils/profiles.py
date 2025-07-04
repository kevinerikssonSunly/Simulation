from typing import Any
import pandas as pd
from models.resource import Wind, PV


def get_profiles(wind_cap, solar_cap, profile_file) -> tuple[Any, Any]:
    df = pd.read_excel(profile_file)

    df.set_index('Hour', inplace=True)

    wind_profile = df['wind_profile']
    solar_profile = df['solar_profile']

    wind = Wind(wind_cap, wind_profile)
    solar = PV(solar_cap, solar_profile)

    wind_prod = wind.get_production()
    solar_prod = solar.get_production()

    return wind_prod, solar_prod