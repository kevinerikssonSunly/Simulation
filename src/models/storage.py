from interfaces.StorageUnit import StorageUnit


class Storage(StorageUnit):
    def __init__(self, charge_MW, storage_volume_MWh, round_trip_eff):
        self.max_charge = charge_MW
        self.max_volume = storage_volume_MWh
        self.charge_eff = self.discharge_eff = round_trip_eff**0.5
        self.soc = 0
        self.total_charged_wind = 0
        self.total_charged_solar = 0

    def charge(self, to_charge_wind_MWh, to_charge_solar_MWh):
        total_to_charge = to_charge_wind_MWh + to_charge_solar_MWh
        max_raw_capacity = (self.max_volume - self.soc) / self.charge_eff
        chargeable_raw = min(total_to_charge, self.max_charge, max_raw_capacity)

        if total_to_charge == 0:
            return 0.0, 0.0, 0.0

        wind_fraction = to_charge_wind_MWh / total_to_charge
        solar_fraction = to_charge_solar_MWh / total_to_charge

        wind_charged = chargeable_raw * wind_fraction
        solar_charged = chargeable_raw * solar_fraction

        redundant_wind = max(to_charge_wind_MWh - wind_charged, 0.0)
        redundant_solar = max(to_charge_solar_MWh - solar_charged, 0.0)

        self.total_charged_wind += wind_charged
        self.total_charged_solar += solar_charged

        charged = chargeable_raw * self.charge_eff
        self.soc += charged
        cycle_loss = chargeable_raw - charged

        return chargeable_raw, redundant_wind, redundant_solar, cycle_loss

    def discharge(self, needed_energy_MWh):
        possible_discharge = min(self.max_charge, self.soc)
        required_discharge = needed_energy_MWh / self.discharge_eff
        discharged = min(possible_discharge, required_discharge)
        self.soc -= discharged
        delivered = discharged * self.discharge_eff
        cycle_loss = discharged - delivered
        return delivered, cycle_loss