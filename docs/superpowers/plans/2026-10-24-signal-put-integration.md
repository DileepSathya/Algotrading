# Signal-date put integration

Approved scope: enrich all three live Higher High signal CSV exports using the
last completed option candle of each signal's IST session. Keep stock calculations
unchanged. Retain unmatched signals with blank option columns.

- [x] Derive exact candle request dates from each signal date, separately from
  the three-month expiry discovery range.
- [x] Select nearest expiry, moving to the next when within five calendar days.
- [x] Select one PE using final-session delta in [-0.40, -0.35], nearest -0.375;
  break ties with strike then symbol. Classify expiry month against signal date.
- [x] Cache enrichment by underlying/date and contract lists by underlying/expiry.
- [x] Export identical ordered headers to all, current-month and current-day CSVs.
- [x] Add mocked retrieval and export regression checks.

## Data conventions and limits

The historical API supports expired contracts only. Per the updated requirement,
signals whose selected expiry is active use `put_option_retrival.py` for current
snapshot delta/IV. Expired contracts retain signal-date historical Greeks. The
live downloader accepts an explicit expiry so it does not recalculate the
signal-date expiry rule against today's date. Live snapshots are cached by
underlying/expiry and use the same authentication and request limiter. Stock
signal dates and prices remain unchanged; active option Greeks are current,
not historical. Today's signals use the live route as well.

Expired contract lookup supplies expiry dates and symbols, not strike metadata
or expiry timestamps. Strike is parsed from the exact underlying/expiry prefix;
unrecognized formats are logged and skipped. `expiry_timestamp` is derived as
the Unix timestamp of 15:30 Asia/Kolkata on the returned expiry date, not copied
from the historical API. IV uses `implied_volatility` (or `iv`) without rescaling.

Daily historical resolution is used: `D` for active-contract history and `1D`
for expired-contract history. `put_entry_price` records the selected option's
daily close on the stock signal's IST date. Active contracts use the regular
history endpoint after live contract selection; expired contracts use the close
and Greeks from their daily historical candle. Timestamp matching accepts daily
candles stamped at midnight. Missing, non-finite, non-positive, wrong-date or
incomplete daily closes are left blank; current LTP is never substituted.
Today's daily close is requested only after 15:30 IST. Price requests are cached
by exact option symbol and signal date. All three CSVs have the additional
`put_entry_price` column immediately after `put_symbol`. No real account requests
are performed by the regression tests.

Historical expiry discovery is capped at yesterday because Fyers rejects current
and future end dates. Active expiry dates are supplemented from option-chain
metadata and cached per underlying. All historical-provider API requests are
paced at least 0.3 seconds apart; explicit -360 responses retry twice with
exponential backoff. Bare equity symbols are normalized to NSE:<symbol>-EQ for
API calls, while exported stock symbols are preserved.
