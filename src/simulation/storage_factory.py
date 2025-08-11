from typing import List, Dict
from interfaces.StorageUnit import StorageUnit
from models.storage import Storage

def create_storages(battery_config: Dict, bess_rte) -> List[StorageUnit]:
    storages = []

    for duration, charge_mw in battery_config.items():
        volume = charge_mw * duration
        storages.append(Storage(charge_mw, volume, bess_rte, name=f"BESS {duration}h"))

    storages.sort(key=lambda s: (-s.max_charge, s.max_volume))  # High MW, then depth

    return storages