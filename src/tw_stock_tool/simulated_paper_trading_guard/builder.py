from typing import Callable
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig, GuardConfigError
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision
from tw_stock_tool.simulated_paper_trading_guard.adapter import SimulatedPaperTradingGuardAdapter
from tw_stock_tool.risk.builder import build_risk_decision_provider_from_config
from tw_stock_tool.kill_switch.models import KillSwitchState

GuardDecisionProvider = Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision]

def build_guard_decision_provider_from_config(
    config: SimulatedPaperTradingGuardConfig | None,
) -> GuardDecisionProvider:
    if config is not None and not isinstance(config, SimulatedPaperTradingGuardConfig):
        raise GuardConfigError("config must be a SimulatedPaperTradingGuardConfig or None.")

    if config is not None and config.kill_switch_enabled is True:
        raise GuardConfigError("kill_switch_enabled=True is not supported in the config builder yet.")

    risk_config = config.risk if config is not None else None
    risk_provider = build_risk_decision_provider_from_config(risk_config)

    # For now, kill switch is always disabled when built from config
    # (since True raises an error above, and None/False map to inactive).
    kill_switch_state = KillSwitchState(is_active=False)

    # The reference price provider logic used in backtesting engine:
    # We will use the order metadata price if it exists, otherwise 0.0 (though it should exist).
    # Since adapter requires a Callable, we provide a simple one.
    def reference_price_provider(order: SimulatedOrder, portfolio: SimulatedPortfolio) -> float:
        return float(order.metadata.get("price", 0.0))

    adapter = SimulatedPaperTradingGuardAdapter(
        kill_switch_state=kill_switch_state,
        reference_price_provider=reference_price_provider,
        risk_decision_provider=risk_provider,
    )

    return adapter
