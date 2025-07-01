from constraints import BESS_STORAGE_VOLUME_MW, BESS_1h_CHARGE_MW, BESS_2h_CHARGE_MW, BESS_4h_CHARGE_MW, BESS_6h_CHARGE_MW, BESS_8h_CHARGE_MW, BESS_DISCHARGE_MW
from models.storage import PumpedHydroStorage, BatteryStorage

def simulate_dispatch_per_year(wind_prod, solar_prod, baseload, wind_cap, solar_cap):
    results_by_year = []

    years = wind_prod.index.year.unique()

    for year in years:
        print(f"\n=== Year {year} ===")
        wind_year = wind_prod[wind_prod.index.year == year]
        solar_year = solar_prod[solar_prod.index.year == year]
        hours = len(wind_year.index)
        storage: BatteryStorage = BatteryStorage(BESS_1h_CHARGE_MW, BESS_STORAGE_VOLUME_MW)

        produced_total = 0
        hours_met = 0
        redundant_wind_total = 0.0
        redundant_solar_total = 0.0
        wasted_energy_total = 0.0
        missing_energy_total = 0.0
        wind_in_baseload = 0.0
        solar_in_baseload = 0.0
        wind_total = wind_year.sum()
        solar_total = solar_year.sum()
        charged_wind = 0
        charged_solar = 0

        for i in range(hours):
            wind_gen = wind_year.iloc[i]
            solar_gen = solar_year.iloc[i]
            total_gen = wind_gen + solar_gen

            if total_gen >= baseload:
                wind_in_baseload += baseload * (wind_gen / total_gen)
                solar_in_baseload += baseload * (solar_gen / total_gen)
                produced_total += baseload
                hours_met += 1

                total_surplus = total_gen - baseload
                wind_surplus, solar_surplus = allocate_surplus(wind_gen, solar_gen, total_surplus)
                charged, redundant_wind_share, redundant_solar_share = storage.charge(wind_surplus, solar_surplus)
                charged_wind += wind_surplus - redundant_wind_share
                charged_solar += solar_surplus - redundant_solar_share
                redundant_wind_total += redundant_wind_share
                redundant_solar_total += redundant_solar_share
                wasted_energy_total += max(total_surplus - charged, 0)
            else:
                shortfall = baseload - total_gen
                discharged = storage.discharge(shortfall)
                produced = total_gen + discharged
                produced_total += produced

                if produced == baseload:
                    hours_met += 1
                else:
                    missing_energy_total += baseload - produced


        wind_total_in_baseload = wind_in_baseload + storage.total_charged_wind
        solar_total_in_baseload = solar_in_baseload + storage.total_charged_solar

        expected_baseload = baseload * hours

        actual_green_baseload_hours = hours_met / hours

        green_energy_share = produced_total / expected_baseload
        wind_energy_share = wind_total_in_baseload / produced_total
        solar_energy_share = solar_total_in_baseload / produced_total

        redundant_wind_share = redundant_wind_total / wind_total
        redundant_solar_share = redundant_solar_total / solar_total
        excess_energy = (redundant_wind_total + redundant_solar_total) / expected_baseload

        missing_energy_share = missing_energy_total / expected_baseload

        result = {
            "year": year,
            "wind_capacity": round(wind_cap),
            "solar_capacity": round(solar_cap),
            "BESS_1h_CHARGE_MW": round(BESS_1h_CHARGE_MW),
            "BESS_2h_CHARGE_MW": "",
            "BESS_4h_CHARGE_MW": "",
            "BESS_6h_CHARGE_MW": "",
            "BESS_8h_CHARGE_MW": "",
            "pumped Hydro": "",
            "baseload": baseload,
            "wind_total": round(wind_total),
            "solar_total": round(solar_total),
            "redundant_wind_total": round(redundant_wind_total),
            "redundant_solar_total": round(redundant_solar_total),
            "missing_energy_total": round(missing_energy_total),
            "green_energy_share": round(green_energy_share * 100, 0),
            "actual_green_baseload_hours": round(actual_green_baseload_hours * 100, 0),
            "redundant_wind_share": round(redundant_wind_share * 100, 0),
            "redundant_solar_share": round(redundant_solar_share * 100, 0),
            "excess_energy": round(excess_energy * 100, 0),
        }

        summarize_results(result, wind_cap, solar_cap, baseload)
        results_by_year.append(result)

    return results_by_year


def allocate_surplus(wind, solar, surplus):
    total_gen = wind + solar
    if total_gen == 0:
        return 0, 0
    wind_surplus = surplus * (wind / total_gen)
    solar_surplus = surplus * (solar / total_gen)
    return wind_surplus, solar_surplus

def summarize_results(result, wind_cap, solar_cap, baseload):
    print(f"Simulation Results for Year {result['year']}")
    print("=" * 50)
    print(f"Wind Capacity (MW):               {result['wind_capacity']}")
    print(f"Solar Capacity (MW):              {result['solar_capacity']}")
    print()
    print(f"BESS 1h Charge Power (MW):        {result['BESS_1h_CHARGE_MW']}")
    print(f"BESS 2h Charge Power (MW):        {result['BESS_2h_CHARGE_MW']}")
    print(f"BESS 4h Charge Power (MW):        {result['BESS_4h_CHARGE_MW']}")
    print(f"BESS 6h Charge Power (MW):        {result['BESS_6h_CHARGE_MW']}")
    print(f"BESS 8h Charge Power (MW):        {result['BESS_8h_CHARGE_MW']}")
    print(f"Pumped Hydro (MW):                {result['pumped Hydro']}")
    print()
    print(f"Baseload:                         {result['baseload']}")
    print(f"Total Wind Energy (MWh):          {result['wind_total']}")
    print(f"Total Solar Energy (MWh):         {result['solar_total']}")
    print(f"Redundant Wind Energy (MWh):      {result['redundant_wind_total']}")
    print(f"Redundant Solar Energy (MWh):     {result['redundant_solar_total']}")
    print(f"Missing Energy (MWh):             {result['missing_energy_total']}")
    print()
    print(f"Green Energy Share (%):           {result['green_energy_share']}")
    print(f"Actual Green Baseload Hours:      {result['actual_green_baseload_hours']}")
    print()
    print(f"Redundant Wind %:             {result['redundant_wind_share']}")
    print(f"Redundant Solar %:            {result['redundant_solar_share']}")
    print(f"Excess Energy (MWh):              {result['excess_energy']}")


