
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import math
import re
import time

import pandas as pd

from fyers_apiv3 import fyersModel
from src import logger
from src.configurations.config import config_manager


class HistoricalOptionData:

    DELTA_MIN = -0.40
    DELTA_MAX = -0.35

    def _request(self, endpoint, payload):
        """Stay below 50 requests/minute; allow the server window to reset."""
        for attempt in range(3):
            last = self.__dict__.get('_last_request_at')
            if last is not None:
                time.sleep(max(0, 1.3 - (time.monotonic() - last)))
            self._last_request_at = time.monotonic()
            response = endpoint(data=payload)
            if str(response.get('code')) != '-360' or attempt == 2:
                return response
            message = str(response.get('message', '')).lower()
            if 'minute' in message or 'second' not in message:
                logger.warning('Fyers minute quota reached; waiting 61 seconds before retry (%s/2)', attempt + 1)
                # Other stages or processes may already have consumed the quota.
                # Retry the same payload after a full window, not after 1-2 sec.
                time.sleep(30)
                time.sleep(31)
            else:
                logger.warning('Fyers per-second quota reached; retrying request (%s/2)', attempt + 1)
                time.sleep(2 ** attempt)

    @staticmethod
    def normalize_underlying(symbol):
        symbol = symbol.strip().upper()
        if ':' not in symbol:
            return 'NSE:' + symbol if symbol.endswith('-EQ') else f'NSE:{symbol}-EQ'
        return symbol

    def get_active_expiries(self, underlying):
        """Use the live chain only for expiry metadata, never historical Greeks."""
        cache = self.__dict__.setdefault('_active_expiry_cache', {})
        if underlying not in cache:
            response = self._request(self.fyers.optionchain, {
                'symbol': underlying, 'strikecount': 1, 'timestamp': ''})
            if response.get('s') != 'ok':
                logger.error('Active expiry lookup failed for %s: %s', underlying, response)
                return []
            cache[underlying] = [datetime.strptime(item['date'], '%d-%m-%Y').date().isoformat()
                                 for item in response.get('data', {}).get('expiryData', [])]
        return cache[underlying]

    def get_live_put(self, underlying, expiry, signal_day):
        """Fetch active contracts via the live downloader, caching each snapshot."""
        from .put_option_retrival import DataRetrieval

        cache = self.__dict__.setdefault('_live_put_cache', {})
        key = (underlying, expiry.isoformat())
        if key not in cache:
            # Reuse authentication and the shared request limiter.
            downloader = DataRetrieval.__new__(DataRetrieval)
            downloader.fyers = self.fyers
            logger.info('Retrieving current put snapshot for %s expiry %s; stock signal date %s',
                        underlying, expiry, signal_day)
            cache[key] = downloader.get_option_chain_data(
                symbol=underlying, expiry_date=expiry, request=self._request,
                allow_nearest_delta=True)
        frame = cache[key]
        if frame.empty:
            return {}
        row = frame.iloc[0]
        month_diff = (expiry.year - signal_day.year) * 12 + expiry.month - signal_day.month
        return {
            'put_symbol': row['symbol'], 'expiry': expiry.isoformat(),
            'expiry_timestamp': row['expiry_timestamp'], 'strike': row['strike_price'],
            'delta': row['delta'], 'iv': row['iv'],
            'put_entry_price': self.get_daily_close(row['symbol'], signal_day),
            'expiry_month': {0: 'current_month', 1: 'next_month'}.get(month_diff, 'other_month'),
        }

    @staticmethod
    def now():
        return pd.Timestamp.now(tz='Asia/Kolkata')

    @staticmethod
    def valid_close(value):
        try:
            price = float(value)
            return price if math.isfinite(price) and price > 0 else None
        except (TypeError, ValueError):
            return None

    def get_daily_close(self, option_symbol, signal_day):
        """Read the exact active option's completed daily close on the entry date."""
        now = self.now()
        if signal_day > now.date() or (signal_day == now.date() and
                                       now < now.normalize() + pd.Timedelta(hours=15, minutes=30)):
            logger.warning('Daily option candle is incomplete for %s on %s', option_symbol, signal_day)
            return None
        cache = self.__dict__.setdefault('_daily_close_cache', {})
        key = (option_symbol, signal_day.isoformat())
        if key not in cache:
            cache[key] = None
            try:
                response = self._request(self.fyers.history, {
                    'symbol': option_symbol, 'resolution': 'D', 'date_format': '1',
                    'range_from': key[1], 'range_to': key[1], 'cont_flag': '0'})
                if response.get('s') == 'ok':
                    for candle in response.get('candles', []):
                        candle_day = pd.to_datetime(candle[0], unit='s', utc=True).tz_convert('Asia/Kolkata').date()
                        if candle_day == signal_day:
                            cache[key] = self.valid_close(candle[4])
                else:
                    logger.warning('Daily option history failed for %s on %s: %s', option_symbol, signal_day, response)
                    cache.pop(key, None)
                    return None
            except Exception:
                logger.exception('Daily option close retrieval failed for %s on %s', option_symbol, signal_day)
                cache.pop(key, None)
                return None
            if cache[key] is None:
                logger.warning('No valid daily option close for %s on %s', option_symbol, signal_day)
            else:
                logger.info('Recorded daily put close: %s | signal date %s | close %s',
                            option_symbol, signal_day, cache[key])
        return cache[key]

    def select_for_signal(self, underlying, signal_date):
        """Use historical session Greeks for expired contracts, live for active ones.

        Candle ranges are exactly the signal's IST date. Expiry discovery covers
        three months separately. Expiry timestamps use 15:30 IST (market close),
        since the expired-contract endpoint supplies dates, not epoch timestamps.
        """
        underlying = self.normalize_underlying(underlying)
        stamp = pd.Timestamp(signal_date)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert('Asia/Kolkata')
        day = stamp.date()
        if day > self.today():
            logger.warning('Cannot select put for future signal date %s: %s', day, underlying)
            return {}
        start = day.isoformat()
        desired_end = (pd.Timestamp(day) + pd.DateOffset(months=3)).date()
        discovery_end = min(desired_end, self.today() - timedelta(days=1))
        expiries = (list(self.get_expiries(underlying, start, discovery_end.isoformat()))
                    if day <= discovery_end else [])
        if desired_end >= self.today():
            expiries.extend(self.get_active_expiries(underlying))
        # Active expiries must remain in the list: removing them first could
        # silently select a different contract than the one required by the rule.
        upcoming = sorted({pd.Timestamp(value).date() for value in expiries
                           if pd.Timestamp(value).date() >= day})
        if not upcoming:
            logger.warning('No expiry available for %s on %s', underlying, day)
            return {}
        index = 1 if (upcoming[0] - day).days <= 5 else 0
        if index >= len(upcoming):
            logger.warning('No later expiry for %s on %s', underlying, day)
            return {}
        expiry = upcoming[index]
        if expiry >= self.today():
            return self.get_live_put(underlying, expiry, day)
        cache = self.__dict__.setdefault('_signal_contract_cache', {})
        key = (underlying, expiry.isoformat())
        if key not in cache:
            cache[key] = self.get_expired_put_symbols(*key)
        matches = []
        for contract in cache[key]:
            try:
                history = self.get_contract_history(contract, start, start, resolution='1D')
                if history.empty or 'delta' not in history or 'timestamp' not in history:
                    continue
                times = pd.to_datetime(history['timestamp'], utc=True).dt.tz_convert('Asia/Kolkata')
                # Daily candles may be stamped at midnight rather than 09:15.
                valid = history.loc[times.dt.date == day]
                if valid.empty:
                    continue
                last = valid.loc[times.loc[valid.index].idxmax()]
                delta = float(last['delta'])
                if not self.DELTA_MIN <= delta <= self.DELTA_MAX:
                    continue
                strike = self.contract_strike(underlying, contract, expiry)
                iv = last.get('implied_volatility', last.get('iv'))
                iv = float(iv) if iv is not None and pd.notna(iv) else None
                if iv is not None and not math.isfinite(iv):
                    iv = None
                month_diff = (expiry.year - day.year) * 12 + expiry.month - day.month
                matches.append({
                    'put_symbol': contract, 'expiry': expiry.isoformat(),
                    'expiry_timestamp': str(int(pd.Timestamp(f'{expiry} 15:30', tz='Asia/Kolkata').timestamp())),
                    'strike': strike, 'delta': delta, 'iv': iv,
                    'put_entry_price': self.valid_close(last.get('close')),
                    'expiry_month': {0: 'current_month', 1: 'next_month'}.get(month_diff, 'other_month'),
                })
            except Exception:
                logger.exception('Historical put lookup failed for %s on %s', contract, day)
        if not matches:
            logger.warning('No session-close put matched delta range for %s on %s', underlying, day)
            return {}
        return min(matches, key=lambda row: (abs(row['delta'] + 0.375), row['strike'], row['put_symbol']))

    @staticmethod
    def contract_strike(underlying, contract, expiry):
        """Remove the exact underlying and expiry prefix before parsing strike."""
        root = underlying.split('-')[0]
        monthly = root + expiry.strftime('%y%b').upper()
        month_code = '123456789OND'[expiry.month - 1]
        weekly = root + expiry.strftime('%y') + month_code + expiry.strftime('%d')
        for prefix in (monthly, weekly):
            if contract.startswith(prefix) and contract.endswith('PE'):
                value = contract[len(prefix):-2]
                if re.fullmatch(r'\d+(?:\.\d+)?', value):
                    return float(value)
        raise ValueError(f'Cannot identify strike in {contract} for {underlying}, {expiry}')

    def __init__(self):
        client_id, access_token = config_manager.authentication()

        self.fyers = fyersModel.FyersModel(
            client_id=client_id,
            is_async=False,
            token=access_token,
            log_path=""
        )

    @staticmethod
    def today():
        return datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).date()

    def get_expiries(
        self,
        underlying: str,
        start_date: str,
        end_date: str
    ):
        """Retrieve historical option expiry dates."""

        payload = {
            "symbol": underlying,
            "range_from": start_date,
            "range_to": end_date,
            "date_format": "1"
        }

        # The historical endpoint rejects current or future range boundaries.
        end = min(pd.Timestamp(end_date).date(), self.today() - timedelta(days=1))
        if pd.Timestamp(start_date).date() > end:
            return []
        payload['range_to'] = end.isoformat()
        payload['symbol'] = self.normalize_underlying(underlying)
        response = self._request(self.fyers.expiry_dates, payload)

        if response.get("s") != "ok":
            logger.error(f"Expiry request failed: {response}")
            return []

        expiry_dates = (
            response.get("data", {})
            .get("expiry_dates", {})
            .get("options", [])
        )

        print("\nAvailable historical expiries:")
        for expiry in expiry_dates:
            print(expiry)

        return expiry_dates

    def get_expired_put_symbols(
        self,
        underlying: str,
        expiry_date: str
    ):
        """Retrieve PUT symbols for a particular expiry."""

        payload = {
            "symbol": underlying,
            "expiry_date": expiry_date
        }

        payload['symbol'] = self.normalize_underlying(underlying)
        response = self._request(self.fyers.history_underlying_symbols, payload)

        if response.get("s") != "ok":
            logger.error(
                f"Contract lookup failed for {expiry_date}: "
                f"{response}"
            )
            return []

        symbols = (
            response.get("data", {})
            .get("contracts", {})
            .get("options", [])
        )

        # Keep PUT contracts only.
        return [
            symbol for symbol in symbols
            if symbol.upper().endswith("PE")
        ]

    def get_contract_history(
        self,
        option_symbol: str,
        start_date: str,
        end_date: str,
        resolution: str = "5"
    ):
        """Download OHLCV, OI and historical Greeks."""

        payload = {
            "symbol": option_symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": start_date,
            "range_to": end_date,
            "include_oi": 1,
            "include_greeks": 1
        }

        response = self._request(self.fyers.fno_historical_data, payload)

        if response.get("s") == "no_data":
            return pd.DataFrame()

        if response.get("s") != "ok":
            logger.warning(
                f"History failed for {option_symbol}: "
                f"{response}"
            )
            return pd.DataFrame()

        # Use API-provided column names. Optional columns
        # may vary according to the requested flags.
        columns = response.get("columns", [])
        candles = response.get("candles", [])

        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles, columns=columns)

        # Convert candle timestamps to Indian market time.
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="s",
            utc=True
        ).dt.tz_convert("Asia/Kolkata")

        df["symbol"] = option_symbol

        return df

    def download(
        self,
        underlying: str,
        start_date: str,
        end_date: str,
        resolution: str = "5",
        output_file: str = "historical_puts.csv"
    ):
        """
        Download expired PUT contracts and retain candles
        whose historical delta lies within the target range.
        """

        # Validate date strings.
        start = datetime.strptime(
            start_date, "%Y-%m-%d"
        ).date()

        end = datetime.strptime(
            end_date, "%Y-%m-%d"
        ).date()

        if start > end:
            raise ValueError(
                "start_date must not be after end_date."
            )

        if end >= self.today():
            raise ValueError(
                "Use a completed historical date range. "
                "This endpoint supports expired contracts only."
            )

        # Intraday API requests are limited to 100 days each.
        if resolution not in ("1D", "1W", "1M"):
            if (end - start).days > 99:
                raise ValueError(
                    "For this resolution, use a date range "
                    "of at most 100 calendar days per request."
                )

        expiries = self.get_expiries(
            underlying,
            start_date,
            end_date
        )

        if not expiries:
            print("No historical expiries returned.")
            return pd.DataFrame()

        matching_frames = []

        for expiry in expiries:

            print(f"\nProcessing expiry: {expiry}")

            put_symbols = self.get_expired_put_symbols(
                underlying,
                expiry
            )

            print(f"PUT contracts found: {len(put_symbols)}")

            for index, option_symbol in enumerate(
                put_symbols, start=1
            ):
                print(
                    f"[{index}/{len(put_symbols)}] "
                    f"Downloading {option_symbol}"
                )

                history = self.get_contract_history(
                    option_symbol=option_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    resolution=resolution
                )

                if history.empty:
                    continue

                if "delta" not in history.columns:
                    logger.warning(
                        f"No delta column for {option_symbol}"
                    )
                    continue

                history["delta"] = pd.to_numeric(
                    history["delta"],
                    errors="coerce"
                )

                # Keep only candles where historical delta
                # falls inside the specified range.
                mask = history["delta"].between(
                    self.DELTA_MIN,
                    self.DELTA_MAX,
                    inclusive="both"
                )

                filtered = history.loc[mask].copy()

                if filtered.empty:
                    continue

                filtered["expiry"] = expiry

                matching_frames.append(filtered)

        if not matching_frames:
            print(
                "\nNo historical PUT candles matched "
                f"delta {self.DELTA_MIN} to {self.DELTA_MAX}."
            )
            return pd.DataFrame()

        result = pd.concat(
            matching_frames,
            ignore_index=True
        )

        # Save results.
        output_path = Path(output_file)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        result.to_csv(output_path, index=False)

        print(f"\nTotal matching candles: {len(result)}")
        print(f"Saved to: {output_path.resolve()}")

        return result


if __name__ == "__main__":

    downloader = HistoricalOptionData()

    historical_puts = downloader.download(
        underlying="NSE:SBIN-EQ",
        start_date="2026-08-01",
        end_date="2026-08-31",
        resolution="5",
        output_file="artifacts/historical_sbin_puts.csv"
    )

    if not historical_puts.empty:
        print("\nSample results:")
        print(historical_puts.head(10).to_string(index=False))
