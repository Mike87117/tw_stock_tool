from pathlib import Path

import mplfinance as mpf
import numpy as np
import pandas as pd


def plot_stock_chart(
    df: pd.DataFrame,
    stock_id: str,
    symbol: str,
    save_path: Path | None = None,
) -> None:
    plot_df = df.copy().dropna(subset=["Open", "High", "Low", "Close"])

    buy_y = np.where(plot_df["Signal"] == "BUY", plot_df["Low"] * 0.98, np.nan)
    sell_y = np.where(plot_df["Signal"] == "SELL", plot_df["High"] * 1.02, np.nan)

    add_plots = [
        mpf.make_addplot(plot_df["MA5"], color="#1f77b4"),
        mpf.make_addplot(plot_df["MA20"], color="#ff7f0e"),
        mpf.make_addplot(plot_df["MA60"], color="#2ca02c"),
        mpf.make_addplot(plot_df["BB_Upper"], color="gray", linestyle="dashed"),
        mpf.make_addplot(plot_df["BB_Middle"], color="gray", linestyle="solid"),
        mpf.make_addplot(plot_df["BB_Lower"], color="gray", linestyle="dashed"),
        mpf.make_addplot(plot_df["RSI"], panel=2, color="purple", ylabel="RSI"),
        mpf.make_addplot(plot_df["MACD"], panel=3, color="blue", ylabel="MACD"),
        mpf.make_addplot(plot_df["MACD_Signal"], panel=3, color="orange"),
        mpf.make_addplot(plot_df["MACD_Hist"], panel=3, type="bar", color="dimgray", alpha=0.7),
    ]

    if np.isfinite(buy_y).any():
        add_plots.append(
            mpf.make_addplot(buy_y, type="scatter", marker="^", markersize=60, color="red")
        )
    if np.isfinite(sell_y).any():
        add_plots.append(
            mpf.make_addplot(sell_y, type="scatter", marker="v", markersize=60, color="green")
        )

    kwargs = {}
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["savefig"] = dict(fname=str(save_path), dpi=130)

    mpf.plot(
        plot_df,
        type="candle",
        style="yahoo",
        title=f"{stock_id} ({symbol}) Technical Chart",
        volume=True,
        addplot=add_plots,
        panel_ratios=(6, 2, 2, 3),
        figscale=1.2,
        figratio=(16, 10),
        tight_layout=True,
        datetime_format="%Y-%m",
        xrotation=12,
        **kwargs,
    )
