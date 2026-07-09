from dataclasses import dataclass
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig

class GuardConfigError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class SimulatedPaperTradingGuardConfig:
    risk: SimulatedPaperTradingRiskConfig | None = None
    kill_switch_enabled: bool | None = None

    def __post_init__(self):
        if self.risk is not None and not isinstance(self.risk, SimulatedPaperTradingRiskConfig):
            raise GuardConfigError("risk must be a SimulatedPaperTradingRiskConfig object.")
            
        if self.kill_switch_enabled is not None and not isinstance(self.kill_switch_enabled, bool):
            raise GuardConfigError("kill_switch_enabled must be a boolean.")
