from dataclasses import dataclass
import math

class RiskConfigError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class SimulatedPaperTradingRiskConfig:
    max_order_notional: float | None = None
    max_position_quantity: int | None = None
    max_position_notional: float | None = None
    max_total_exposure: float | None = None

    def __post_init__(self):
        # Validate max_order_notional
        if self.max_order_notional is not None:
            if isinstance(self.max_order_notional, bool):
                raise RiskConfigError("max_order_notional cannot be a boolean.")
            if not isinstance(self.max_order_notional, (int, float)):
                raise RiskConfigError("max_order_notional must be numeric.")
            if not math.isfinite(self.max_order_notional):
                raise RiskConfigError("max_order_notional must be finite.")
            if self.max_order_notional <= 0:
                raise RiskConfigError("max_order_notional must be strictly positive.")

        # Validate max_position_notional
        if self.max_position_notional is not None:
            if isinstance(self.max_position_notional, bool):
                raise RiskConfigError("max_position_notional cannot be a boolean.")
            if not isinstance(self.max_position_notional, (int, float)):
                raise RiskConfigError("max_position_notional must be numeric.")
            if not math.isfinite(self.max_position_notional):
                raise RiskConfigError("max_position_notional must be finite.")
            if self.max_position_notional <= 0:
                raise RiskConfigError("max_position_notional must be strictly positive.")

        # Validate max_position_quantity
        if self.max_position_quantity is not None:
            if isinstance(self.max_position_quantity, bool):
                raise RiskConfigError("max_position_quantity cannot be a boolean.")
            if not isinstance(self.max_position_quantity, int):
                raise RiskConfigError("max_position_quantity must be an integer.")
            if self.max_position_quantity <= 0:
                raise RiskConfigError("max_position_quantity must be strictly positive.")

        # Validate max_total_exposure
        if self.max_total_exposure is not None:
            if isinstance(self.max_total_exposure, bool):
                raise RiskConfigError("max_total_exposure cannot be a boolean.")
            if not isinstance(self.max_total_exposure, (int, float)):
                raise RiskConfigError("max_total_exposure must be numeric.")
            if not math.isfinite(self.max_total_exposure):
                raise RiskConfigError("max_total_exposure must be finite.")
            if self.max_total_exposure <= 0:
                raise RiskConfigError("max_total_exposure must be strictly positive.")
