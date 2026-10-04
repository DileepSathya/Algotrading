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
EMA_PERIOD = 9
EMA_PERIOD_VOL = 20
# --------------------------------------------------
# Target configuration
# --------------------------------------------------
TARGET_PERCENT = 10.0
# --------------------------------------------------
# Backtest configuration
# --------------------------------------------------
DEFAULT_DATA = PROJECT_ROOT / "artifacts/backtest/hist_data_D.json"
DEFAULT_REPORTS = PROJECT_ROOT / "artifacts/backtest_reports"
INITIAL_CAPITAL = 100_000.0
MAX_OPEN_POSITIONS = 4
EXIT_EMA_PERIOD = 10
