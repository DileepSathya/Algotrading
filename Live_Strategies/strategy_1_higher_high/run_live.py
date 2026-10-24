
import json
from pathlib import Path

import pandas as pd

from src import logger
from src.components.fyers_login import fyers_login
from src.components.data_retrieval import DataRetrieval
from src.components.strategy import HigherHighStrategy


BASE_DIR = Path(__file__).resolve().parent
HIST_DATA_PATH = BASE_DIR / "artifacts" / "hist_data_D.json"


def login():
    try:
        logger.info("----- Login Stage -----")
        fyers_login.login()
        logger.info("Login successful")
    except Exception:
        logger.exception("Login failed")
        raise


def user_data_retriever():
    try:
        logger.info("----- User Information Stage -----")
        data = DataRetrieval()
        data.userdata()
        data.hist_data()
        logger.info("Data retrieval successful")
    except Exception:
        logger.exception("Data retrieval failed")
        raise


def generate_signals():
    try:
        logger.info("----- Higher High Signal Generation -----")

        with open(HIST_DATA_PATH, "r", encoding="utf-8") as file:
            historical_data = json.load(file)

        df = pd.DataFrame(historical_data)

        strategy = HigherHighStrategy()
        strategy.save_signals_to_csv(df)

        logger.info("Signal generation successful")

    except Exception:
        logger.exception("Signal generation failed")
        raise


if __name__ == "__main__":
    login()
    choice = input("retrive new data : ").lower()
    if choice == "y" :

        user_data_retriever()
    else:
        pass
    generate_signals()
