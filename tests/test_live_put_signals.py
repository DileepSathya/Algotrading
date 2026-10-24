import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Live_Strategies/strategy_1_higher_high'))
from src.components.historical_put_option import HistoricalOptionData
from src.components.strategy import HigherHighStrategy
from src.components.put_option_retrival import DataRetrieval as LivePutData


class HistoricalPutTests(unittest.TestCase):
    def provider(self):
        provider = HistoricalOptionData.__new__(HistoricalOptionData)
        provider.fyers = Mock()
        provider.today = lambda: date(2026, 10, 24)
        provider.get_expiries = Mock(return_value=['2026-08-27', '2026-09-29'])
        provider.get_active_expiries = Mock(return_value=[])
        provider.get_live_put = Mock(return_value={})
        provider.get_daily_close = Mock(return_value=12.5)
        provider.get_expired_put_symbols = Mock(return_value=['NSE:SBIN26SEP800PE'])
        provider.get_contract_history = Mock(return_value=pd.DataFrame({
            'timestamp': pd.to_datetime(['2026-08-24 09:15', '2026-08-24 15:25']).tz_localize('Asia/Kolkata'),
            'delta': [-0.375, -0.38], 'implied_volatility': [22, 24], 'close': [11, 12.5],
        }))
        return provider

    def test_signal_date_ranges_rollover_and_last_candle(self):
        provider = self.provider()
        result = provider.select_for_signal('NSE:SBIN-EQ', '2026-08-24')
        self.assertEqual(result['expiry'], '2026-09-29')
        self.assertEqual(result['expiry_month'], 'next_month')
        self.assertEqual(result['strike'], 800)
        self.assertEqual(result['delta'], -0.38)
        self.assertEqual(result['iv'], 24)
        self.assertEqual(result['expiry_timestamp'], str(int(pd.Timestamp('2026-09-29 15:30', tz='Asia/Kolkata').timestamp())))
        self.assertEqual(result['put_entry_price'], 12.5)
        provider.get_contract_history.assert_called_once_with('NSE:SBIN26SEP800PE', '2026-08-24', '2026-08-24', resolution='1D')
        self.assertGreater(provider.get_expiries.call_args.args[2], '2026-09-29')

    def test_no_earlier_matching_delta_fallback(self):
        provider = self.provider()
        provider.get_contract_history.return_value.loc[1, 'delta'] = -0.5
        self.assertEqual(provider.select_for_signal('NSE:SBIN-EQ', '2026-08-24'), {})

    def test_year_rollover_and_delta_boundaries(self):
        provider = self.provider()
        provider.today = lambda: date(2027, 3, 1)
        provider.get_expiries.return_value = ['2026-12-29', '2027-01-26']
        provider.get_expired_put_symbols.return_value = ['NSE:SBIN27JAN800PE']
        for delta in (-0.4, -0.35):
            provider.get_contract_history.return_value = pd.DataFrame({
                'timestamp': [pd.Timestamp('2026-12-24 15:25', tz='Asia/Kolkata')],
                'delta': [delta], 'iv': [20]})
            result = provider.select_for_signal('NSE:SBIN-EQ', '2026-12-24')
            self.assertEqual(result['expiry_month'], 'next_month')
            self.assertEqual(result['delta'], delta)

    def test_active_expiry_does_not_fetch_historical_greeks(self):
        provider = self.provider()
        provider.get_expiries.return_value = ['2026-10-29', '2026-11-24']
        self.assertEqual(provider.select_for_signal('NSE:SBIN-EQ', '2026-10-23'), {})
        self.assertEqual(provider.select_for_signal('NSE:SBIN-EQ', '2026-10-24'), {})
        provider.get_contract_history.assert_not_called()

    def test_missing_last_delta_and_wrong_day_are_not_replaced(self):
        provider = self.provider()
        provider.get_contract_history.return_value.loc[1, 'delta'] = None
        self.assertEqual(provider.select_for_signal('NSE:SBIN-EQ', '2026-08-24'), {})
        self.assertEqual(provider.select_for_signal('NSE:SBIN-EQ', '2026-08-25'), {})

    def test_exact_api_payload_and_timestamp_conversion(self):
        provider = self.provider()
        provider.fyers.fno_historical_data.return_value = {'s': 'ok',
            'columns': ['timestamp', 'delta', 'implied_volatility'],
            'candles': [[int(pd.Timestamp('2026-08-24 15:25', tz='Asia/Kolkata').timestamp()), -0.38, 24]]}
        actual = HistoricalOptionData.get_contract_history(provider, 'NSE:SBIN26SEP800PE',
                                                          '2026-08-24', '2026-08-24')
        payload = provider.fyers.fno_historical_data.call_args.kwargs['data']
        self.assertEqual(payload['range_from'], '2026-08-24')
        self.assertEqual(payload['range_to'], '2026-08-24')
        self.assertEqual(payload['include_greeks'], 1)
        self.assertEqual(actual.iloc[0]['timestamp'].hour, 15)

    def test_empty_and_failed_enrichment_keep_export_headers(self):
        strategy = HigherHighStrategy()
        for empty in (False, True):
            candles = pd.DataFrame([] if empty else [{'date': pd.Timestamp.now(tz='Asia/Kolkata').normalize(),
                'symbol': 'NSE:SBIN-EQ', 'trade_signal': True, 'close': 820,
                'low': 800, strategy.ema_column: 790}])
            strategy.prepare_data = Mock(return_value=candles)
            provider = Mock()
            provider.select_for_signal.side_effect = RuntimeError('API unavailable')
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'signals.csv'
                strategy.save_signals_to_csv(candles, option_provider=provider, output_path=output)
                data = pd.read_csv(output)
                self.assertEqual(len(data), 0 if empty else 1)
                self.assertIn('expiry_month', data.columns)
                if not empty:
                    self.assertTrue(pd.isna(data.iloc[0]['put_symbol']))

    def test_export_schema_and_repeated_signal_cache(self):
        strategy = HigherHighStrategy()
        candles = pd.DataFrame([{'date': pd.Timestamp.now(tz='Asia/Kolkata').normalize(), 'symbol': 'NSE:SBIN-EQ',
            'trade_signal': True, 'close': 820, 'low': 800, strategy.ema_column: 790}] * 2)
        strategy.prepare_data = Mock(return_value=candles)
        provider = self.provider()
        provider.select_for_signal = Mock(return_value={'put_symbol': 'NSE:SBIN26SEP800PE', 'delta': -0.38,
                                                      'put_entry_price': 12.5})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'higher_high_signals.csv'
            strategy.save_signals_to_csv(candles, option_provider=provider, output_path=output)
            data = pd.read_csv(output)
            self.assertEqual(list(data.columns), ['date', 'symbol', 'symbol_entry_price', 'symbol_SL_price',
                'symbol_TG_price', 'put_symbol', 'put_entry_price', 'expiry', 'expiry_timestamp', 'strike', 'delta', 'iv', 'expiry_month'])
            self.assertEqual(len(data), 2)
            self.assertEqual(data['put_entry_price'].tolist(), [12.5, 12.5])
            for filename in ('current_month_signals.csv', 'current_day_signals.csv'):
                self.assertEqual(list(pd.read_csv(Path(directory) / filename).columns), list(data.columns))
        provider.select_for_signal.assert_called_once()

    def test_only_current_month_and_year_trigger_put_retrieval(self):
        strategy = HigherHighStrategy()
        current = pd.Timestamp.now(tz='Asia/Kolkata').normalize().replace(day=1)
        dates = [current, current - pd.DateOffset(months=1), current - pd.DateOffset(years=1)]
        candles = pd.DataFrame([{'date': day, 'symbol': 'NSE:SBIN-EQ',
            'trade_signal': True, 'close': 820, 'low': 800, strategy.ema_column: 790}
            for day in dates])
        strategy.prepare_data = Mock(return_value=candles)
        provider = Mock()
        provider.select_for_signal.return_value = {'put_symbol': 'MATCH'}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'signals.csv'
            strategy.save_signals_to_csv(candles, option_provider=provider, output_path=output)
            data = pd.read_csv(output)
            self.assertEqual(len(data), 3)
            self.assertEqual(data['put_symbol'].notna().sum(), 1)
            self.assertEqual(len(pd.read_csv(Path(directory) / 'current_month_signals.csv')), 1)
        provider.select_for_signal.assert_called_once_with('NSE:SBIN-EQ', current.date().isoformat())

    def test_discovery_caps_at_yesterday_and_keeps_active_expiry(self):
        provider = self.provider()
        provider.get_expiries.return_value = []
        provider.get_active_expiries.return_value = ['2026-10-29', '2026-11-24']
        self.assertEqual(provider.select_for_signal('ADANIPORTS', '2026-10-09'), {})
        provider.get_expiries.assert_called_once_with('NSE:ADANIPORTS-EQ', '2026-10-09', '2026-10-23')
        provider.get_active_expiries.assert_called_once_with('NSE:ADANIPORTS-EQ')
        provider.get_contract_history.assert_not_called()

    def test_rate_limit_retry_and_request_pacing(self):
        provider = self.provider()
        endpoint = Mock(side_effect=[{'s': 'error', 'code': -360}, {'s': 'ok'}])
        with patch('src.components.historical_put_option.time.monotonic', return_value=100), \
             patch('src.components.historical_put_option.time.sleep') as sleep:
            self.assertEqual(provider._request(endpoint, {'symbol': 'X'}), {'s': 'ok'})
            self.assertEqual(endpoint.call_count, 2)
            self.assertTrue(any(call.args[0] >= 1 for call in sleep.call_args_list))
            self.assertTrue(any(call.args[0] >= 0.25 for call in sleep.call_args_list))

    def test_minute_rate_limit_waits_for_window_reset(self):
        provider = self.provider()
        endpoint = Mock(side_effect=[{'s': 'error', 'code': -360,
            'message': 'Standard plan limit of 50 requests/minute'}, {'s': 'ok'}])
        with patch('src.components.historical_put_option.time.monotonic', return_value=100), \
             patch('src.components.historical_put_option.time.sleep') as sleep:
            self.assertEqual(provider._request(endpoint, {}), {'s': 'ok'})
            self.assertGreaterEqual(sum(call.args[0] for call in sleep.call_args_list), 61)

    def test_transient_history_failure_is_not_cached_as_missing_price(self):
        provider = self.provider()
        del provider.get_daily_close
        stamp = int(pd.Timestamp('2026-10-12', tz='Asia/Kolkata').timestamp())
        provider._request = Mock(side_effect=[{'s': 'error', 'code': -360},
            {'s': 'ok', 'candles': [[stamp, 10, 14, 9, 12.5, 100]]}])
        self.assertIsNone(provider.get_daily_close('OPTION', date(2026, 10, 12)))
        self.assertEqual(provider.get_daily_close('OPTION', date(2026, 10, 12)), 12.5)

    def test_historical_expiry_payload_never_reaches_today(self):
        provider = self.provider()
        provider.fyers.expiry_dates.return_value = {'s': 'ok', 'data': {'expiry_dates': {'options': []}}}
        HistoricalOptionData.get_expiries(provider, 'BHEL', '2026-10-06', '2027-01-06')
        payload = provider.fyers.expiry_dates.call_args.kwargs['data']
        self.assertEqual(payload['range_to'], '2026-10-23')
        self.assertEqual(payload['symbol'], 'NSE:BHEL-EQ')

    def test_active_expiry_routes_to_live_component(self):
        provider = self.provider()
        provider.get_expiries.return_value = []
        provider.get_active_expiries.return_value = ['2026-10-27', '2026-11-24']
        provider.get_live_put.return_value = {'put_symbol': 'LIVE', 'delta': -0.38}
        result = provider.select_for_signal('DRREDDY', '2026-10-12')
        self.assertEqual(result['put_symbol'], 'LIVE')
        provider.get_live_put.assert_called_once_with('NSE:DRREDDY-EQ', date(2026, 10, 27), date(2026, 10, 12))
        provider.get_contract_history.assert_not_called()

    def test_today_routes_to_live_without_historical_expiry_request(self):
        provider = self.provider()
        provider.get_active_expiries.return_value = ['2026-10-27', '2026-11-24']
        provider.get_live_put.return_value = {'put_symbol': 'NEXT'}
        self.assertEqual(provider.select_for_signal('DRREDDY', '2026-10-24'), {'put_symbol': 'NEXT'})
        provider.get_expiries.assert_not_called()
        provider.get_live_put.assert_called_once_with('NSE:DRREDDY-EQ', date(2026, 11, 24), date(2026, 10, 24))

    def test_live_component_uses_signal_selected_expiry_and_caches(self):
        provider = self.provider()
        del provider.get_live_put
        provider.fyers.optionchain.side_effect = [
            {'s': 'ok', 'data': {'expiryData': [
                {'date': '27-10-2026', 'expiry': '1793095200'},
                {'date': '24-11-2026', 'expiry': '1795514400'}]}},
            {'s': 'ok', 'data': {'optionsChain': [
                {'option_type': 'PE', 'symbol': 'NSE:DRREDDY26OCT1200PE',
                 'strike_price': 1200, 'greeks': {'delta': -0.38, 'iv': 24}}]}}
        ]
        with patch('src.components.historical_put_option.time.sleep'):
            result = provider.get_live_put('NSE:DRREDDY-EQ', date(2026, 10, 27), date(2026, 10, 12))
            provider.get_live_put('NSE:DRREDDY-EQ', date(2026, 10, 27), date(2026, 10, 14))
        self.assertEqual(result['expiry'], '2026-10-27')
        self.assertEqual(result['expiry_month'], 'current_month')
        self.assertEqual(result['iv'], 24)
        self.assertEqual(result['put_entry_price'], 12.5)
        self.assertEqual(provider.get_daily_close.call_count, 2)
        self.assertEqual(provider.fyers.optionchain.call_count, 2)
        self.assertEqual(provider.fyers.optionchain.call_args.kwargs['data']['timestamp'], '1793095200')

    def test_active_daily_close_uses_exact_contract_date_and_cache(self):
        provider = self.provider()
        del provider.get_daily_close
        stamp = int(pd.Timestamp('2026-10-12', tz='Asia/Kolkata').timestamp())
        provider.fyers.history.return_value = {'s': 'ok', 'candles': [
            [stamp - 86400, 1, 2, 1, 999, 10], [stamp, 10, 14, 9, 12.5, 100]]}
        self.assertEqual(provider.get_daily_close('NSE:DRREDDY26OCT1200PE', date(2026, 10, 12)), 12.5)
        self.assertEqual(provider.get_daily_close('NSE:DRREDDY26OCT1200PE', date(2026, 10, 12)), 12.5)
        provider.fyers.history.assert_called_once_with(data={
            'symbol': 'NSE:DRREDDY26OCT1200PE', 'resolution': 'D', 'date_format': '1',
            'range_from': '2026-10-12', 'range_to': '2026-10-12', 'cont_flag': '0'})

    def test_daily_price_missing_or_incomplete_never_uses_ltp(self):
        provider = self.provider()
        del provider.get_daily_close
        provider.fyers.history.return_value = {'s': 'ok', 'candles': []}
        self.assertIsNone(provider.get_daily_close('EMPTY', date(2026, 10, 12)))
        provider.now = lambda: pd.Timestamp('2026-10-24 12:00', tz='Asia/Kolkata')
        self.assertIsNone(provider.get_daily_close('TODAY', date(2026, 10, 24)))
        self.assertEqual(provider.fyers.history.call_count, 1)

    def test_expired_daily_midnight_candle_is_valid(self):
        provider = self.provider()
        provider.get_contract_history.return_value = pd.DataFrame({
            'timestamp': [pd.Timestamp('2026-08-24 00:00', tz='Asia/Kolkata')],
            'delta': [-0.38], 'close': [13.25], 'iv': [22]})
        result = provider.select_for_signal('SBIN', '2026-08-24')
        self.assertEqual(result['put_entry_price'], 13.25)
        self.assertEqual(result['delta'], -0.38)

    def test_invalid_daily_price_does_not_replace_contract_metadata(self):
        provider = self.provider()
        provider.get_contract_history.return_value['close'] = float('nan')
        result = provider.select_for_signal('SBIN', '2026-08-24')
        self.assertIsNone(result['put_entry_price'])
        self.assertEqual(result['put_symbol'], 'NSE:SBIN26SEP800PE')

    def test_live_fallback_uses_nearest_only_when_no_delta_matches(self):
        for deltas, expected in [([-0.27, -0.57], -0.27), ([-0.42, -0.26], -0.42),
                                 ([-0.41, -0.24], -0.41), ([-0.38, -0.41], -0.38)]:
            downloader = LivePutData.__new__(LivePutData)
            downloader.fyers = Mock()
            response = {'s': 'ok', 'data': {
                'expiryData': [{'date': '27-10-2026', 'expiry': '1793095800'}],
                'optionsChain': [{'symbol': f'PUT{i}', 'option_type': 'PE', 'strike_price': 100 + i,
                                  'greeks': {'delta': delta, 'iv': 20}} for i, delta in enumerate(deltas)]}}
            downloader.fyers.optionchain.return_value = response
            result = downloader.get_option_chain_data('NSE:BHEL-EQ', expiry_date='2026-10-27',
                                                      allow_nearest_delta=True)
            self.assertEqual(result.iloc[0]['delta'], expected)

    def test_live_strict_mode_still_rejects_outside_range(self):
        downloader = LivePutData.__new__(LivePutData)
        downloader.fyers = Mock()
        downloader.fyers.optionchain.return_value = {'s': 'ok', 'data': {
            'expiryData': [{'date': '27-10-2026', 'expiry': '1793095800'}],
            'optionsChain': [{'symbol': 'PUT', 'option_type': 'PE', 'strike_price': 100,
                              'greeks': {'delta': -0.42}}]}}
        result = downloader.get_option_chain_data('NSE:BHEL-EQ', expiry_date='2026-10-27')
        self.assertTrue(result.empty)


if __name__ == '__main__':
    unittest.main()
