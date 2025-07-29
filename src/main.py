import pandas as pd

from config import PROFILES_EE
from simulation.simulate import run_all_scenarios


if __name__ == "__main__":
    path = PROFILES_EE
    df_profiles = pd.read_excel(path)
    wind_profile = df_profiles['wind_profile']
    solar_profile = df_profiles['solar_profile']
    run_all_scenarios(PROFILES_EE, wind_profile, solar_profile, 40)

'''
    baseload = 40#input("Enter baseload (MW): ")
    wind_cap = 183#input("Wind Capacity (MW)")
    solar_cap = 40#input("Solar Capacity (MW)")
    battery_1h = 0#input("1h Battery Capacity (MW)")
    battery_2h = 0#input("2h Battery Capacity (MW)")
    battery_4h = 144#input("4h Battery Capacity (MW)")
    battery_6h = 0#input("6h Battery Capacity (MW)")
    battery_8h = 0#input("8h Battery Capacity (MW)")
    hydro_storage = 0#input("Hydro Storage (MW)")

    run_all_scenarios(wind_profile, solar_profile, baseload)
'''