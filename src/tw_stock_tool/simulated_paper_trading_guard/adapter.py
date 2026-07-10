import math
from typing import Callable
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.risk.models import RiskInputSnapshot, RiskDecision
from tw_stock_tool.kill_switch.models import KillSwitchState
from tw_stock_tool.kill_switch.decisions import evaluate_kill_switch
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision, SimulatedPaperTradingGuardError
from tw_stock_tool.simulated_paper_trading_guard.evaluator import evaluate_simulated_paper_trading_guard

ReferencePriceProvider = Callable[[SimulatedOrder, SimulatedPortfolio], float]
RiskDecisionProvider = Callable[[RiskInputSnapshot], RiskDecision]
PortfolioExposureProvider = Callable[
    [SimulatedOrder, SimulatedPortfolio],
    float,
]


class SimulatedPaperTradingGuardAdapter:
    """
    Stateless bridge adapter connecting the simulated paper trading engine
    to Risk and Kill Switch components.
    """
    def __init__(
        self,
        kill_switch_state: KillSwitchState,
        reference_price_provider: ReferencePriceProvider,
        risk_decision_provider: RiskDecisionProvider,
        *,
        portfolio_exposure_provider: PortfolioExposureProvider | None = None,
    ) -> None:
        if not isinstance(kill_switch_state, KillSwitchState):
            raise SimulatedPaperTradingGuardError("kill_switch_state must be a KillSwitchState object.")
        if not callable(reference_price_provider):
            raise SimulatedPaperTradingGuardError("reference_price_provider must be callable.")
        if not callable(risk_decision_provider):
            raise SimulatedPaperTradingGuardError("risk_decision_provider must be callable.")
        if portfolio_exposure_provider is not None and not callable(portfolio_exposure_provider):
            raise SimulatedPaperTradingGuardError("portfolio_exposure_provider must be callable or None.")

        self.kill_switch_state = kill_switch_state
        self.reference_price_provider = reference_price_provider
        self.risk_decision_provider = risk_decision_provider
        self.portfolio_exposure_provider = portfolio_exposure_provider

    def __call__(self, order: SimulatedOrder, portfolio: SimulatedPortfolio) -> SimulatedPaperTradingGuardDecision:
        if not isinstance(order, SimulatedOrder):
            raise SimulatedPaperTradingGuardError("order must be a SimulatedOrder.")
        if not isinstance(portfolio, SimulatedPortfolio):
            raise SimulatedPaperTradingGuardError("portfolio must be a SimulatedPortfolio.")

        ref_price = self.reference_price_provider(order, portfolio)
        if not isinstance(ref_price, (int, float)) or isinstance(ref_price, bool) or ref_price <= 0:
            raise SimulatedPaperTradingGuardError("reference_price_provider must return a positive number.")

        pos_model = portfolio.position_for(order.symbol)
        current_pos_quantity = pos_model.quantity
        current_pos_notional = float(current_pos_quantity * ref_price)

        if self.portfolio_exposure_provider is not None:
            exp = self.portfolio_exposure_provider(order, portfolio)
            if type(exp) is bool or type(exp).__name__ in ("bool", "bool_"):
                raise SimulatedPaperTradingGuardError("portfolio_exposure_provider must not return a boolean.")
            if not isinstance(exp, (int, float)):
                raise SimulatedPaperTradingGuardError("portfolio_exposure_provider must return a numeric value.")
            if not math.isfinite(exp):
                raise SimulatedPaperTradingGuardError("portfolio_exposure_provider must return a finite value.")
            if exp < 0:
                raise SimulatedPaperTradingGuardError("portfolio_exposure_provider must return a non-negative value.")
            total_exposure = float(exp)
        else:
            # For Phase 42.1, support the current single-symbol simulated paper trading case.
            # Calculate total_exposure from the order symbol's current position only.
            total_exposure = current_pos_notional

        current_open_positions = sum(1 for p in portfolio.positions.values() if p.quantity > 0)

        snapshot = RiskInputSnapshot(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=float(ref_price),
            cash=float(portfolio.cash),
            current_position_quantity=current_pos_quantity,
            current_position_notional=current_pos_notional,
            total_exposure=total_exposure,
            current_open_positions=current_open_positions,
            metadata={
                "order_id": order.order_id,
                "signal_time": str(order.signal_time),
            }
        )

        risk_decision = self.risk_decision_provider(snapshot)
        if not isinstance(risk_decision, RiskDecision):
            raise SimulatedPaperTradingGuardError("risk_decision_provider must return a RiskDecision.")

        kill_switch_decision = evaluate_kill_switch(self.kill_switch_state)

        return evaluate_simulated_paper_trading_guard(risk_decision, kill_switch_decision)
