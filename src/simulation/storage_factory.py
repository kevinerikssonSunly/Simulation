from typing import List, Dict
from interfaces.StorageUnit import StorageUnit
from models.storage import Storage

def create_storages(battery_config: Dict, hydro_config: Dict, bess_rte, hydro_rte) -> List[StorageUnit]:
    storages = []

    for duration, charge_mw in battery_config.items():
        volume = charge_mw * duration
        storages.append(Storage(charge_mw, volume, bess_rte, name=f"BESS {duration}h"))

    if hydro_config["enabled"]:
        storages.append(Storage(hydro_config["charge_mw"], hydro_config["volume_mwh"], hydro_rte, name="Hydro"))

    storages.sort(key=lambda s: s.max_charge)

    return storages