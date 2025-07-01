



class Wind:
    def __init__(self, capacity_mw, profile_mw_mwh):
        self.cap = capacity_mw
        self.profile = profile_mw_mwh

    def get_production(self):
        return self.cap * self.profile
class PV:
    def __init__(self, capacity_mw, profile_mw_mwh):
        self.cap = capacity_mw
        self.profile = profile_mw_mwh

    def get_production(self):
        return self.cap * self.profile