import os
import json
from pathlib import Path
import pandas as pd
import requests
from src import logger
from fyers_apiv3 import fyersModel
from src.configurations.config import config_manager
from datetime import timedelta, date
from src.utils.common import (
    extract_candles_with_symbol,
    save_to_raw_hist_data_json,
    clear_hist_data_json,
    format_symbol
)
from time import sleep


def load_fyers_lot_sizes():
    """
    Downloads the daily FYERS derivative master file and builds a lookup dictionary.
    """
    try:
        logger.info("Downloading daily FYERS F&O symbol master file...")
        url = "https://fyers.in"
        # FYERS master files have no headers: 
        # Column 0: Token, Column 1: Symbol Root Name (e.g., 'SBIN' or 'NIFTY'), Column 2: Lot Size
        df = pd.read_csv(url, header=None, usecols=[0, 1, 2])
        df.columns = ["token", "symbol_root", "lot_size"]
        
        # Create a lookup mapping symbol root names to their respective contract lot sizes
        return dict(zip(df["symbol_root"], df["lot_size"]))
    except Exception as e:
        logger.error(f"Could not download master lot file: {e}. Using baseline fallbacks.")
        # Static baseline fallbacks if network retrieval fails
        return {"SBIN": 1500, "NIFTY": 65, "BANKNIFTY": 30}


class DataRetrieval:

    def __init__(self):
        logger.info("Accessing client_id and access_token")
        client_id, access_token = config_manager.authentication()
        logger.info("Accessing client_id and access_token successful")

        self.fyers = fyersModel.FyersModel(
            client_id=client_id,
            is_async=False,
            token=access_token,
            log_path=""
        )

    def userdata(self):
        logger.info("Fetching user profile data")
        response = self.fyers.get_profile()
        print(response)
        return response

    def hist_data(self, symbol: str, range_from: str, range_to: str, resolution: str = "15"):
        """
        Fetches historical candle data and formats it into a clean Pandas DataFrame.
        """
        logger.info(f"Requesting OHLCV history for {symbol} from {range_from} to {range_to}")
        
        payload = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",     # '1' accepts 'yyyy-mm-dd' strings
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1",       # '1' ensures continuous historical derivatives chains
            "oi_flag": "1"          # '1' appends Open Interest history to each candle
        }
        
        try:
            response = self.fyers.history(data=payload)
            if response.get("s") == "ok":
                candles = response.get("candles", [])
                if not candles:
                    logger.warning(f"No historical candles found for {symbol}")
                    return pd.DataFrame()
                
                columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'open_interest']
                df = pd.DataFrame(candles, columns=columns)
                
                # Format timestamps to readable local format
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
                return df
            else:
                logger.error(f"Failed to retrieve history for {symbol}: {response.get('message')}")
                return pd.DataFrame()
        except Exception as e:
            logger.exception(f"Exception occurred while fetching history data: {e}")
            return pd.DataFrame()

    def get_option_chain_data(self, symbol: str, strike_count: int = 10, expiry_timestamp: str = ""):
        """
        Fetches option chain matrix for a stock or index.
        Categorizes contracts dynamically into ITM / ATM / OTM, and resolves precise 
        lot sizes from the master layout data.
        """
        logger.info(f"Requesting Option Chain data for underlying asset: {symbol}")
        
        # Load active lot sizes from the master manifest file
        lot_size_map = load_fyers_lot_sizes()
        
        # Extract pure stock asset root label (e.g., transforms 'NSE:SBIN-EQ' -> 'SBIN')
        root_stock_name = symbol.replace("NSE:", "").replace("-EQ", "").replace("-INDEX", "")
        lot_size = lot_size_map.get(root_stock_name, "Unknown")

        payload = {
            "symbol": symbol,
            "strikecount": strike_count,
            "timestamp": expiry_timestamp,
            "greeks": "0"
        }
        
        try:
            response = self.fyers.optionchain(data=payload)
            if response.get("s") != "ok":
                logger.error(f"Fyers Option Chain API error: {response.get('message')}")
                return None
                
            chain_data = response.get("data", {})
            underlying_ltp = chain_data.get("index_ltp", 0)
            options_list = chain_data.get("optionsChain", [])
            
            logger.info(f"Successfully retrieved option chain. Underlying LTP: {underlying_ltp}")
            
            # --- CALCULATE ATM STRIKE BOUNDARY ---
            strikes = [opt["strike_price"] for opt in options_list if opt.get("strike_price")]
            if strikes:
                atm_strike = min(strikes, key=lambda x: abs(x - underlying_ltp))
            else:
                atm_strike = None
            
            processed_chain = []
            
            for option in options_list:
                if not option.get("option_type"):
                    continue
                    
                opt_type = option["option_type"]  # "CE" or "PE"
                strike = option["strike_price"]
                
                # --- CORRECTED MONEYNESS CLASSIFICATION ENGINE ---
                if strike == atm_strike:
                    moneyness = "ATM"
                elif opt_type == "CE":
                    # For Calls: Higher strikes are Out-of-the-Money
                    moneyness = "OTM" if strike > underlying_ltp else "ITM"
                elif opt_type == "PE":
                    # For Puts: Lower strikes are Out-of-the-Money
                    moneyness = "OTM" if strike < underlying_ltp else "ITM"
                
                processed_item = {
                    "strike_price": strike,
                    "option_type": opt_type,
                    "moneyness": moneyness,
                    "symbol": option.get("symbol"),
                    "ltp": option.get("ltp"),
                    "open_interest_shares": option.get("oi"),
                    "volume_shares": option.get("volume"),
                    "lot_qty_shares": lot_size,
                    "iv": option.get("iv")
                }
                processed_chain.append(processed_item)
                
            return {
                "underlying_ltp": underlying_ltp,
                "indiavix": chain_data.get("indiavix"),
                "expiries": chain_data.get("expiryData", []),
                "options": processed_chain
            }
            
        except Exception as e:
            logger.exception(f"Exception encountered parsing options chain: {e}")
            return None


if __name__ == "__main__":
    # Initialize the data retrieval system
    downloader = DataRetrieval()
    
    # 1. TEST OPTION CHAIN FETCH & PARSING SYSTEM
    target_stock = "NSE:BHEL-EQ" 
    print(f"\n=================== FETCHING LIVE OPTION CHAIN: {target_stock} ===================")
    
    chain_result = downloader.get_option_chain_data(symbol=target_stock, strike_count=5)
    
    if chain_result:
        print(f"Underlying Spot Price: {chain_result['underlying_ltp']}")
        print(f"India VIX: {chain_result['indiavix']}")
        print("\n" + "="*85)
        print(f"{'Strike':<8} | {'Type':<4} | {'Moneyness':<9} | {'LTP':<8} | {'Lot Qty (shares)':<18} | {'Total OI (shares)':<18}")
        print("="*85)
        
        # Display options grouped clean by moneyness type
        for contract in chain_result["options"]:
            print(f"{contract['strike_price']:<8} | "
                  f"{contract['option_type']:<4} | "
                  f"{contract['moneyness']:<9} | "
                  f"{contract['ltp']:<8} | "
                  f"{str(contract['lot_qty_shares']):<18} | "
                  f"{contract['open_interest_shares']:<18}")
        print("="*85)
    else:
        print("Failed to pull option chain structure parameters.")

    # 2. TEST HISTORICAL DATA FETCH SYSTEM
    # Pulling history for a specific contract derived from current rules
    test_historical_contract = "NSE:SBIN26OCT950PE"
    print(f"\n=================== FETCHING HISTORICAL DATA: {test_historical_contract} ===================")
    
    # Retrieves previous 7 days of 15-minute intervals
    df_history = downloader.hist_data(
        symbol=test_historical_contract,
        range_from="2026-10-15",
        range_to="2026-10-22",
        resolution="15"
    )
    
    if not df_history.empty:
        print(df_history.tail(10).to_string(index=False))
        print("================================================================================")
    else:
        print("No historical logs returned. Verify contract string and date range parameters.")
