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
    *,
    reference_price_provider: Callable[[SimulatedOrder, SimulatedPortfolio], float] | None = None,
) -> GuardDecisionProvider:
    if config is not None and not isinstance(config, SimulatedPaperTradingGuardConfig):
        raise GuardConfigError("config must be a SimulatedPaperTradingGuardConfig or None.")

    if config is not None and config.kill_switch_enabled is True:
        raise GuardConfigError("kill_switch_enabled=True is not supported in the config builder yet.")

    risk_config = config.risk if config is not None else None
    
    has_risk = risk_config is not None and any([
        risk_config.max_order_notional is not None,
        risk_config.max_position_quantity is not None,
        risk_config.max_position_notional is not None,
    ])

    if has_risk and reference_price_provider is None:
        raise GuardConfigError("reference_price_provider is required when risk rules are configured.")

    risk_provider = build_risk_decision_provider_from_config(risk_config)

    # For now, kill switch is always disabled when built from config
    # (since True raises an error above, and None/False map to inactive).
    kill_switch_state = KillSwitchState(is_active=False)

    # If no risk rules are configured and no reference price provider is supplied,
    # we can bypass the adapter entirely to avoid inventing a dummy reference price
    # just to satisfy the adapter's RiskInputSnapshot building.
    if not has_risk and reference_price_provider is None:
        def allow_all_provider(order: SimulatedOrder, portfolio: SimulatedPortfolio) -> SimulatedPaperTradingGuardDecision:
            return SimulatedPaperTradingGuardDecision.allow()
        return allow_all_provider

    adapter = SimulatedPaperTradingGuardAdapter(
        kill_switch_state=kill_switch_state,
        reference_price_provider=reference_price_provider, # type: ignore
        risk_decision_provider=risk_provider,
    )

    return adapter
