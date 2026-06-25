from dataclasses import dataclass, field
from typing import Any

@dataclass
class StockCandidate:
    date: Any
    stock: str
    name: str | None
    category: str
    signal: str
    score: float
    close: float | None
    volume_ratio_20d: float | None
    rsi14: float | None
    ma20: float | None
    ma60: float | None
    macd: float | None
    signals: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    status: str = "ok"
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "Date": self.date,
            "Stock": self.stock,
            "Name": self.name,
            "Category": self.category,
            "Signal": self.signal,
            "Score": self.score,
            "Close": self.close,
            "Volume Ratio 20D": self.volume_ratio_20d,
            "RSI14": self.rsi14,
            "MA20": self.ma20,
            "MA60": self.ma60,
            "MACD": self.macd,
            "Signals": "; ".join(self.signals) if self.signals else "",
            "Risks": "; ".join(self.risks) if self.risks else "",
            "Status": self.status,
            "Error": self.error,
        }
