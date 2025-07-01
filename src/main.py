from constraints import coverage_levels, baseload_levels
from simulation.simulate import run_all_scenarios
from utils.data_prep import load_profiles


if __name__ == "__main__":
    df_profiles = load_profiles()
    wind_profile = df_profiles['wind_profile']
    solar_profile = df_profiles['solar_profile']

    run_all_scenarios(wind_profile, solar_profile, baseload_levels, coverage_levels)