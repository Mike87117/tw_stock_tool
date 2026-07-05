"""
Simulated Paper Trading Guard Package.

This package defines the offline structural guard boundary combining
RiskManager and KillSwitch decisions.
"""
from .models import SimulatedPaperTradingGuardDecision, SimulatedPaperTradingGuardError
from .evaluator import evaluate_simulated_paper_trading_guard

__all__ = [
    "SimulatedPaperTradingGuardDecision",
    "SimulatedPaperTradingGuardError",
    "evaluate_simulated_paper_trading_guard",
]
