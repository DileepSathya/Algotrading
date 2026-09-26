from datetime import time

ORB_START = time(9, 15)
ORB_END = time(9, 30)
FORCED_EXIT_TIME = time(14, 30)
RISK_FRACTION = 0.0025
SL_RANGE_MULTIPLIER = 1.0
TARGET_RANGE_MULTIPLIER = 1.5

# New entries are allowed only inside this intraday window.
ENTRY_START_TIME = time(9, 30)
ENTRY_END_TIME = time(11, 30)

# Stop opening new positions after this many stop-loss exits across all symbols.
MAX_STOP_LOSSES_PER_DAY = 2

# Stop opening new positions in one symbol after this many stop-loss exits.
MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY = 2

# When False, run_backtest uses the module-level defaults above (single run).
# When True, run_combinations executes the Cartesian product of COMBINATION_CONFIG.
run_combinations = True

COMBINATION_CONFIG = {
    "ORB_START": [ORB_START],
    "ORB_END": [time(9, 45)],
    "FORCED_EXIT_TIME": [FORCED_EXIT_TIME],
    "SL_RANGE_MULTIPLIER": [1.0],
    "TARGET_RANGE_MULTIPLIER": [1.0,2.0],
    "ENTRY_START_TIME": [ENTRY_START_TIME],
    "ENTRY_END_TIME": [time(11, 30)],
    "MAX_STOP_LOSSES_PER_DAY": [2],
    "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY": [1],
}





"""COMBINATION_CONFIG = {
    "ORB_START": [ORB_START],
    "ORB_END": [time(9, 30),time(10, 00),time(9, 45)],
    "FORCED_EXIT_TIME": [FORCED_EXIT_TIME],
    "SL_RANGE_MULTIPLIER": [0.5,1.0],
    "TARGET_RANGE_MULTIPLIER": [1.0,1.5,2],
    "ENTRY_START_TIME": [ENTRY_START_TIME],
    "ENTRY_END_TIME": [time(11, 30),time(12, 30)],
    "MAX_STOP_LOSSES_PER_DAY": [1,2,3],
    "MAX_STOP_LOSSES_PER_SYMBOL_PER_DAY": [1,2],
}
"""