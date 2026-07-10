import pandas as pd
from tw_stock_tool.paper_trading.models import SimulatedPortfolio
from tw_stock_tool.kill_switch.models import KillSwitchState
from typing import TYPE_CHECKING
from .adapter import SimulatedPaperTradingGuardAdapter, ReferencePriceProvider, RiskDecisionProvider, PortfolioExposureProvider

if TYPE_CHECKING:
    from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult


def run_simulated_paper_trading_with_guard(
    df: pd.DataFrame,
    symbol: str,
    initial_cash: float,
    quantity_per_trade: int,
    kill_switch_state: KillSwitchState,
    reference_price_provider: ReferencePriceProvider,
    risk_decision_provider: RiskDecisionProvider,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    *,
    portfolio_exposure_provider: PortfolioExposureProvider | None = None,
) -> SimulatedPortfolio:
    """
    Run simulated paper trading with guard behavior using explicitly injected providers.

    This acts as a workflow wrapper to instantiate the adapter and pass it into the
    engine without coupling the engine directly to the guard system.
    """
    from tw_stock_tool.paper_trading.engine import run_simulated_paper_trading

    adapter = SimulatedPaperTradingGuardAdapter(
        kill_switch_state=kill_switch_state,
        reference_price_provider=reference_price_provider,
        risk_decision_provider=risk_decision_provider,
        portfolio_exposure_provider=portfolio_exposure_provider,
    )

    return run_simulated_paper_trading(
        df=df,
        symbol=symbol,
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        slippage_per_share=slippage_per_share,
        guard_decision_provider=adapter,
    )


def run_simulated_paper_trading_result_with_guard(
    df: pd.DataFrame,
    symbol: str,
    initial_cash: float,
    quantity_per_trade: int,
    kill_switch_state: KillSwitchState,
    reference_price_provider: ReferencePriceProvider,
    risk_decision_provider: RiskDecisionProvider,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    last_price: float | None = None,
    *,
    portfolio_exposure_provider: PortfolioExposureProvider | None = None,
) -> 'SimulatedPaperTradingResult':
    """
    Run simulated paper trading with guard behavior and build a stable summary result object.

    This acts as a workflow wrapper to instantiate the adapter and pass it into the
    engine result wrapper without coupling the engine directly to the guard system.
    """
    from tw_stock_tool.paper_trading.engine import run_simulated_paper_trading_result

    adapter = SimulatedPaperTradingGuardAdapter(
        kill_switch_state=kill_switch_state,
        reference_price_provider=reference_price_provider,
        risk_decision_provider=risk_decision_provider,
        portfolio_exposure_provider=portfolio_exposure_provider,
    )

    return run_simulated_paper_trading_result(
        df=df,
        symbol=symbol,
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        slippage_per_share=slippage_per_share,
        last_price=last_price,
        guard_decision_provider=adapter,
    )
