from typing import Callable
from tw_stock_tool.risk.models import RiskDecision, RiskInputSnapshot
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig, RiskConfigError
from tw_stock_tool.risk.rules import (
    check_max_order_notional,
    check_max_position_quantity,
    check_max_position_notional,
    check_max_total_exposure,
    combine_risk_decisions,
)

RiskDecisionProvider = Callable[[RiskInputSnapshot], RiskDecision]

def build_risk_decision_provider_from_config(config: SimulatedPaperTradingRiskConfig | None) -> RiskDecisionProvider:
    if config is not None and not isinstance(config, SimulatedPaperTradingRiskConfig):
        raise RiskConfigError("config must be a SimulatedPaperTradingRiskConfig or None.")

    def provider(snapshot: RiskInputSnapshot) -> RiskDecision:
        if config is None:
            return RiskDecision.allow()

        decisions = []

        if config.max_order_notional is not None:
            decisions.append(check_max_order_notional(snapshot, config.max_order_notional))

        if config.max_position_quantity is not None:
            decisions.append(check_max_position_quantity(snapshot, config.max_position_quantity))

        if config.max_position_notional is not None:
            decisions.append(check_max_position_notional(snapshot, config.max_position_notional))

        if config.max_total_exposure is not None:
            decisions.append(check_max_total_exposure(snapshot, config.max_total_exposure))

        if not decisions:
            return RiskDecision.allow()

        return combine_risk_decisions(decisions)

    return provider
