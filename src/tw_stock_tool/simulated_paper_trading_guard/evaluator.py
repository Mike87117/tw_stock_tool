"""
Evaluator logic for the Simulated Paper Trading Guard package.

This module provides pure functional logic to evaluate RiskManager
and KillSwitch decisions and produce a combined structural decision.
"""
from tw_stock_tool.risk.models import RiskDecision
from tw_stock_tool.kill_switch.decisions import KillSwitchDecision
from .models import SimulatedPaperTradingGuardDecision, SimulatedPaperTradingGuardError

def evaluate_simulated_paper_trading_guard(
    risk_decision: RiskDecision,
    kill_switch_decision: KillSwitchDecision,
) -> SimulatedPaperTradingGuardDecision:
    if not isinstance(risk_decision, RiskDecision):
        raise SimulatedPaperTradingGuardError("risk_decision must be a RiskDecision object.")
    
    if not isinstance(kill_switch_decision, KillSwitchDecision):
        raise SimulatedPaperTradingGuardError("kill_switch_decision must be a KillSwitchDecision object.")

    metadata = {
        "risk_allowed": risk_decision.allowed,
        "kill_switch_allowed": kill_switch_decision.is_allowed,
        "risk_reason_count": len(risk_decision.reasons),
        "kill_switch_blocked": kill_switch_decision.is_blocked,
    }

    if risk_decision.allowed and kill_switch_decision.is_allowed:
        return SimulatedPaperTradingGuardDecision.allow(metadata=metadata)

    reasons = []
    if not kill_switch_decision.is_allowed:
        if kill_switch_decision.reason:
            reasons.append(kill_switch_decision.reason)
            
    if not risk_decision.allowed:
        reasons.extend(risk_decision.reasons)

    return SimulatedPaperTradingGuardDecision.block(reasons=reasons, metadata=metadata)
