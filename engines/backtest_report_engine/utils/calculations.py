def calculate_equity_curve(
    pnl_series,
    initial_capital
):
    return (
        initial_capital +
        pnl_series.cumsum()
    )


def calculate_drawdown(equity):
    peak = equity.cummax()

    drawdown = equity - peak

    drawdown_percent = (
        drawdown / peak
    ) * 100

    return drawdown, drawdown_percent