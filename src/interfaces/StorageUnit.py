from abc import ABC, abstractmethod

import pandas as pd


class StorageUnit(ABC):
    def __init__(self):
        self.name = None

    @abstractmethod
    def charge(self, wind: float, solar: float) -> tuple[float, float, float, float]:
        """Returns: charged_energy, redundant_wind, redundant_solar, cycle_loss"""
        pass

    @abstractmethod
    def discharge(self, shortfall: float, timestamp: pd.Timestamp) -> tuple[float, float, float, float]:
        """Returns: discharged_energy, cycle_loss"""
        pass

    @abstractmethod
    def get_average_cycles_per_year(self) -> float:
        """Returns: average cycles per year"""
        pass

    @abstractmethod
    def reset_yearly_energy(self) -> float:
        """Resets yearly energy"""
        pass

    @abstractmethod
    def get_zero_hours(self) -> float:
        """Resets yearly energy"""
        pass

    @abstractmethod
    def reset_yearly_zero_hours(self) -> float:
        """Resets yearly energy"""
        pass