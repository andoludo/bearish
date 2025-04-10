from typing import Optional

import pandas as pd
from plotly.subplots import make_subplots  # type: ignore
import plotly.graph_objects as go  # type: ignore


def plot(
    data: pd.DataFrame,
    symbol: str,
    name: Optional[str] = None,
    dates: Optional[pd.Series] = None,  # type: ignore
) -> go.Figure:
    data.ta.sma(50, append=True)
    data.ta.sma(200, append=True)
    data.ta.adx(append=True)
    data.ta.macd(append=True)
    data.ta.rsi(append=True)
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        specs=[
            [{"rowspan": 2}],  # Row 1: main chart
            [None],  # Row 2: skipped (part of row 1)
            [{}],  # Row 3: RSI
            [{}],  # Row 4: MACD
        ],
        subplot_titles=(
            f"Price + SMAs ({symbol} [{name}])",
            f"RSI ({symbol} [{name}])",
            f"MACD ({symbol} [{name}])",
        ),
    )
    # Row 1: Candlestick + SMAs
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data.open,
            high=data.high,
            low=data.low,
            close=data.close,
            name="Candlestick",
        ),
        row=1,
        col=1,
    )
    fig.update_xaxes(rangeslider_thickness=0.04, row=1, col=1)
    fig.add_trace(
        go.Scatter(x=data.index, y=data.SMA_50, name="SMA 50", mode="lines"),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(x=data.index, y=data.SMA_200, name="SMA 200", mode="lines"),
        row=1,
        col=1,
    )

    # Row 2: RSI
    fig.add_trace(
        go.Scatter(x=data.index, y=data.RSI_14, name="RSI 14", mode="lines"),
        row=3,
        col=1,
    )

    # Row 3: MACD
    fig.add_trace(
        go.Scatter(x=data.index, y=data.MACD_12_26_9, name="MACD", mode="lines"),
        row=4,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=data.index, y=data.MACDs_12_26_9, name="MACD Signal", mode="lines"
        ),
        row=4,
        col=1,
    )

    fig.add_trace(
        go.Bar(x=data.index, y=data.MACDh_12_26_9, name="MACD Histogram", opacity=0.5),
        row=4,
        col=1,
    )
    if dates is not None and not dates.empty:
        for date in dates:
            fig.add_vline(
                x=date, line_dash="dashdot", line_color="MediumPurple", line_width=3
            )

    # Layout tweaks
    fig.update_layout(
        height=900,
        showlegend=True,
        title="Technical Indicator Dashboard",
        margin={"t": 60, "b": 40},
    )

    # Optional: Add horizontal lines for RSI (e.g., 70/30 levels)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    return fig
