"""
Configuration for Strategy-1: Higher High.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

# --------------------------------------------------
# Entry configuration
# --------------------------------------------------
CLOSE_THRESHOLD = 0.70
# --------------------------------------------------
# Indicator configuration
# --------------------------------------------------
PRICE_ABOVE_EMA_PERIOD = True
EMA_PERIOD = 20
EMA_FILTER = True
SMALLER_EMA_PERIOD = 20
BIGGER_EMA_PERIOD = 50
USE_RSI = True
RSI_PERIOD = 10
RSI_MIN_VALUE = 40.0
RSI_MAX_VALUE = 90.0

EMA_PERIOD_VOL = 10
# --------------------------------------------------
# Target configuration
# --------------------------------------------------
TARGET_PERCENT = 7.0
# --------------------------------------------------
# Backtest configuration
# --------------------------------------------------
DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_D.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"
INITIAL_CAPITAL = 100_000.0
MAX_OPEN_POSITIONS = 4
EXIT_EMA_PERIOD = 20
TRAIL_STOP_LOSS = False
TRAIL_STOP_LOSS_CANDLE_COUNT = 2

# Optional OHLCV-only controls for --single. None disables risk/filter limits.
RISK_PER_TRADE_PCT = None  # 0.5 means 0.5% of equity, not 50%.
SIGNAL_RANKING = "alphabetical"  # alphabetical, momentum, relative_volume
MOMENTUM_LOOKBACK = 20
ATR_PERIOD = 14
MAX_EXTENSION_ATR = None
MIN_REWARD_RISK = None

# Running run_backtest.py compares named experiments by default.
RUN_EXPERIMENTS = False
EXPERIMENT_VALIDATION = True
VALIDATION_TRAIN_YEARS = 2
VALIDATION_MIN_TRADES = 30


# When False, RUN_EXPERIMENTS selects comparisons or a single run.
# When True, run_combinations executes the Cartesian product of COMBINATION_CONFIG.
run_combinations = False

COMBINATION_CONFIG = {
    "CLOSE_THRESHOLD": [0.70],
    "EMA_PERIOD": [20],
    "PRICE_ABOVE_EMA_PERIOD": [True, False],
    "EMA_FILTER": [True, False],
    "SMALLER_EMA_PERIOD": [20],
    "BIGGER_EMA_PERIOD": [50],
    "USE_RSI": [True, False],
    "RSI_PERIOD": [10],
    "RSI_MIN_VALUE": [30],
    "RSI_MAX_VALUE": [70.0],
    "EMA_PERIOD_VOL": [10],
    "TARGET_PERCENT": [5.0],
    "MAX_OPEN_POSITIONS": [4],
    "EXIT_EMA_PERIOD": [20],
    "TRAIL_STOP_LOSS": [True],
    "TRAIL_STOP_LOSS_CANDLE_COUNT": [2],
    # None disables the corresponding risk limit or entry filter.
    "RISK_PER_TRADE_PCT": [None, 0.5, 0.75, 1.0],
    "SIGNAL_RANKING": ["alphabetical", "momentum", "relative_volume"],
    "MOMENTUM_LOOKBACK": [20],
    "ATR_PERIOD": [14],
    "MAX_EXTENSION_ATR": [None, 1.5, 2.0],
    "MIN_REWARD_RISK": [None, 1.0, 1.5],
}
# This full Cartesian grid contains 62,208 runs. Reduce lists for a smaller sweep.
