import pandas as pd
from openpyxl import load_workbook
from constraints import PV_CAPACITY_MW, WIND_CAPACITY_MW
from models.resource import Wind, PV
from optimisation.search import simulate_dispatch_per_year


def run_all_scenarios(wind_profile, solar_profile, baseload_levels, coverage_levels):
    excel_path = "/Users/kevineriksson/PycharmProjects/green_baseload_sim/data/Simulator output.xlsx"

    for baseload in baseload_levels:
        print(f"\nRunning simulation for {baseload}MW")

        wind = Wind(WIND_CAPACITY_MW, wind_profile)
        solar = PV(PV_CAPACITY_MW, solar_profile)

        wind_prod = wind.get_production()
        solar_prod = solar.get_production()

        result = simulate_dispatch_per_year(wind_prod, solar_prod, baseload, WIND_CAPACITY_MW, PV_CAPACITY_MW)
        df = pd.DataFrame(result)

        update_sheet(df, excel_path)


def update_sheet(df, wb_path, base_row=5, start_column=2):
    wb = load_workbook(wb_path)
    ws = wb.active

    current_row = base_row
    while ws.cell(row=current_row, column=start_column).value is not None:
        current_row += 1

    for r_idx, row in enumerate(df.itertuples(index=False), start=current_row):
        for c_idx, value in enumerate(row, start=start_column):
            ws.cell(row=r_idx, column=c_idx, value=value)

    wb.save(wb_path)