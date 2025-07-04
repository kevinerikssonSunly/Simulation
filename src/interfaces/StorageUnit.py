from abc import ABC, abstractmethod

class StorageUnit(ABC):
    @abstractmethod
    def charge(self, wind: float, solar: float) -> tuple[float, float, float, float]:
        """Returns: charged_energy, redundant_wind, redundant_solar, cycle_loss"""
        pass

    @abstractmethod
    def discharge(self, shortfall: float) -> tuple[float, float]:
        """Returns: discharged_energy, cycle_loss"""
        pass