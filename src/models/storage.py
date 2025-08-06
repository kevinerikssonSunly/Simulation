from interfaces.StorageUnit import StorageUnit


class Storage(StorageUnit):
    def __init__(self, charge_MW, storage_volume_MWh, round_trip_eff, name):
        self.max_charge = charge_MW
        self.max_volume = storage_volume_MWh
        self.charge_eff = self.discharge_eff = round_trip_eff**0.5
        self.soc = 0
        self.wind_soc = 0
        self.solar_soc = 0
        self.total_charged_wind = 0
        self.total_charged_solar = 0
        self.discharge_limit_per_day = 2*storage_volume_MWh
        self.daily_discharged_energy = 0
        self.yearly_discharged_energy = 0
        self.zero_hours = 0
        self.last_updated_day = None
        self.name = name

    def charge(self, to_charge_wind_MWh, to_charge_solar_MWh):
        total_to_charge = to_charge_wind_MWh + to_charge_solar_MWh
        max_raw_capacity = (self.max_volume - self.soc) / self.charge_eff
        chargeable_raw = min(total_to_charge, self.max_charge, max_raw_capacity)

        if total_to_charge == 0:
            return 0.0, 0.0, 0.0, 0.0

        wind_fraction = to_charge_wind_MWh / total_to_charge
        solar_fraction = to_charge_solar_MWh / total_to_charge

        wind_charged_raw = chargeable_raw * wind_fraction
        solar_charged_raw = chargeable_raw * solar_fraction

        wind_charged = wind_charged_raw * self.charge_eff
        solar_charged = solar_charged_raw * self.charge_eff

        redundant_wind = max(to_charge_wind_MWh - wind_charged_raw, 0.0)
        redundant_solar = max(to_charge_solar_MWh - solar_charged_raw, 0.0)

        self.total_charged_wind += wind_charged_raw
        self.total_charged_solar += solar_charged_raw

        self.soc += wind_charged + solar_charged
        self.wind_soc += wind_charged
        self.solar_soc += solar_charged

        cycle_loss = chargeable_raw - (wind_charged + solar_charged)

        return chargeable_raw, redundant_wind, redundant_solar, cycle_loss

    def discharge(self, needed_energy_MWh, timestamp):
        current_day = timestamp.date()
        if self.last_updated_day != current_day:
            self.daily_discharged_energy = 0.0
            self.last_updated_day = current_day

        remaining_quota = self.discharge_limit_per_day - self.daily_discharged_energy
        if remaining_quota <= 0 or self.soc <= 0:
            if self.soc <= 0:
                self.zero_hours += 1
            return 0.0, 0.0, 0.0, 0.0

        possible_discharge = min(self.max_charge, self.soc)
        required_discharge = needed_energy_MWh / self.discharge_eff
        discharged = min(possible_discharge, required_discharge, remaining_quota)

        wind_fraction = self.wind_soc / self.soc if self.soc > 0 else 0.0
        solar_fraction = self.solar_soc / self.soc if self.soc > 0 else 0.0

        wind_used = discharged * wind_fraction
        solar_used = discharged * solar_fraction

        # Update state of charge and source-specific SoCs
        self.soc -= discharged
        self.wind_soc -= wind_used
        self.solar_soc -= solar_used

        self.daily_discharged_energy += discharged
        self.yearly_discharged_energy += discharged

        delivered = discharged * self.discharge_eff
        wind_delivered = wind_used * self.discharge_eff
        solar_delivered = solar_used * self.discharge_eff

        cycle_loss = discharged - delivered

        if delivered == 0:
            self.zero_hours += 1

        return delivered, wind_delivered, solar_delivered, cycle_loss


    def get_average_cycles_per_year(self):
        return self.yearly_discharged_energy / self.max_volume if self.max_volume > 0 else 0

    def reset_yearly_energy(self):
        self.yearly_discharged_energy = 0.0

    def get_zero_hours(self):
        return self.zero_hours

    def reset_yearly_zero_hours(self):
        self.zero_hours = 0.0

