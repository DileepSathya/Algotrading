"""Read-only diagnostic: show nearest deltas in an expanded live strike range."""
import argparse

from src.components.historical_put_option import HistoricalOptionData


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbols', nargs='+')
    parser.add_argument('--expiry-timestamp', required=True)
    parser.add_argument('--strike-count', type=int, default=10)
    args = parser.parse_args()
    provider = HistoricalOptionData()
    for symbol in args.symbols:
        underlying = provider.normalize_underlying(symbol)
        response = provider._request(provider.fyers.optionchain, {
            'symbol': underlying, 'strikecount': args.strike_count,
            'timestamp': args.expiry_timestamp, 'greeks': '1'})
        puts = [row for row in response.get('data', {}).get('optionsChain', [])
                if row.get('option_type') == 'PE']
        deltas = []
        for row in puts:
            try:
                delta = float((row.get('greeks') or {}).get('delta'))
                deltas.append((row.get('symbol'), row.get('strike_price'), delta))
            except (TypeError, ValueError):
                continue
        deltas.sort(key=lambda row: abs(row[2] + 0.375))
        if response.get('s') != 'ok':
            print({'api_error': response})
        print({'underlying': underlying, 'status': response.get('s'),
               'message': response.get('message'), 'puts': len(puts),
               'with_delta': len(deltas), 'nearest_deltas': deltas[:5]})


if __name__ == '__main__':
    main()
