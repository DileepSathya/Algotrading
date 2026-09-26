from Backtest.backtest_engine import (
    BacktestEngine,
    HistoricalDataLoader,
)

from Backtest.Strategies.Strategy_1_higher_high import (
    HigherHighStrategy,
)

from engines.trade_engine import TradeEngine

from engines.exit_engine import (
    ExitEngine,
    TargetExit,
    SLExit,
    EMAExit,
)

from engines.position_sizing_engine import (
    PositionSizingEngine,
)

from engines.backtest_report_engine import (
    BacktestReportEngine,
)


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = (
    "D:/FM/ALGOTRADING/"
    "artifacts/backtest/hist_data_D.json"
)

# Initial trading capital
INITIAL_CAPITAL = 100000

# Maximum number of simultaneously open positions
MAX_OPEN_POSITIONS = 4

# Enable / disable position sizing
#
# True:
#   - Capital allocation is applied.
#   - Quantity is calculated from capital allocation.
#   - Maximum open positions is enforced.
#
# False:
#   - Legacy behaviour.
#   - Quantity = 1.
#   - Position sizing engine is not used.
#
USE_POSITION_SIZING = True


# ============================================================
# LOAD HISTORICAL DATA
# ============================================================

df = HistoricalDataLoader.load_json(
    DATA_PATH
)

#df=df[df['date']>="2026-01-01"]
# ============================================================
# CREATE STRATEGY
# ============================================================

strategy = HigherHighStrategy()


# ============================================================
# CREATE TRADE ENGINE
# ============================================================

trade_engine = TradeEngine()


# ============================================================
# CREATE EXIT ENGINE
# ============================================================

exit_engine = ExitEngine(
    rules=[
        TargetExit(),
        SLExit(),
        EMAExit(10),
    ]
)


# ============================================================
# CREATE POSITION SIZING ENGINE
# ============================================================

position_sizing_engine = None

if USE_POSITION_SIZING:

    position_sizing_engine = PositionSizingEngine(
        initial_capital=INITIAL_CAPITAL,
        max_open_positions=MAX_OPEN_POSITIONS,
    )


# ============================================================
# CREATE BACKTEST ENGINE
# ============================================================

backtest_engine = BacktestEngine(
    strategy=strategy,
    trade_engine=trade_engine,
    exit_engine=exit_engine,
    position_sizing_engine=position_sizing_engine,
)


# ============================================================
# RUN BACKTEST
# ============================================================

result = backtest_engine.run(df)


# ============================================================
# GET COMPLETED TRADES
# ============================================================

trades_df = result.to_dataframe()


# ============================================================
# PRINT COMPLETED TRADES
# ============================================================

print("\n")
print("=" * 80)
print("COMPLETED TRADES")
print("=" * 80)

if trades_df.empty:
    print("No completed trades.")

else:
    print(trades_df.to_string(index=False))


# ============================================================
# POSITION SIZING CONFIGURATION
# ============================================================

print("\n")
print("=" * 80)
print("POSITION SIZING CONFIGURATION")
print("=" * 80)

if USE_POSITION_SIZING:

    capital_per_position = (
        INITIAL_CAPITAL
        / MAX_OPEN_POSITIONS
    )

    print("Position Sizing       : ENABLED")
    print(
        f"Initial Capital      : "
        f"₹{INITIAL_CAPITAL:,.2f}"
    )
    print(
        f"Max Open Positions   : "
        f"{MAX_OPEN_POSITIONS}"
    )
    print(
        f"Starting Capital / Position: "
        f"₹{capital_per_position:,.2f}"
    )

else:

    print("Position Sizing       : DISABLED")
    print("Quantity Mode         : 1 share per trade")


# ============================================================
# CREATE BACKTEST REPORT
# ============================================================

report_engine = BacktestReportEngine(
    trades_df=trades_df,
    capital=INITIAL_CAPITAL,
    strategy_name=strategy.__class__.__name__,
    reports_root=(
        "D:/FM/ALGOTRADING/"
        "artifacts/backtest_reports"
    ),
)

report, report_folder = report_engine.generate_and_save()


# ============================================================
# PRINT BACKTEST REPORT
# ============================================================

print("\n")
print("=" * 80)
print("BACKTEST REPORT")
print("=" * 80)

print(report)
print(f"Report saved to        : {report_folder.resolve()}")


# ============================================================
# POSITION SIZING FINAL STATE
# ============================================================

if USE_POSITION_SIZING:

    print("\n")
    print("=" * 80)
    print("POSITION SIZING FINAL STATE")
    print("=" * 80)

    print(
        f"Open Positions       : "
        f"{position_sizing_engine.get_open_positions()}"
    )

    print(
        f"Allocated Capital    : "
        f"₹{position_sizing_engine.get_allocated_capital():,.2f}"
    )

    print(
        f"Available Capital    : "
        f"₹{position_sizing_engine.get_available_capital():,.2f}"
    )

    print(
        f"Max Open Positions   : "
        f"{position_sizing_engine.get_max_open_positions()}"
    )

    # ----------------------------------------------
    # Active positions
    # ----------------------------------------------

    active_positions = (
        position_sizing_engine.get_active_positions()
    )

    print("\nActive Positions:")

    if not active_positions:

        print("None")

    else:

        for symbol, position in active_positions.items():

            print(
                f"  {symbol} | "
                f"Entry: ₹{position.entry_price:,.2f} | "
                f"Quantity: {position.quantity} | "
                f"Allocated: "
                f"₹{position.allocated_capital:,.2f}"
            )


# ============================================================
# END
# ============================================================

print("\n")
print("=" * 80)
print("BACKTEST COMPLETED")
print("=" * 80)
