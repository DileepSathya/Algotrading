
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src import logger
from fyers_apiv3 import fyersModel
from src.configurations.config import config_manager


class DataRetrieval:

    DELTA_MIN = -0.40
    DELTA_MAX = -0.35
    EXPIRY_THRESHOLD_DAYS = 5

    def __init__(self):
        logger.info("Accessing client_id and access_token")

        client_id, access_token = config_manager.authentication()

        self.fyers = fyersModel.FyersModel(
            client_id=client_id,
            is_async=False,
            token=access_token,
            log_path=""
        )

        logger.info("Fyers client initialized successfully")

    def userdata(self):
        """Fetch the authenticated user's profile."""
        response = self.fyers.get_profile()
        print(response)
        return response

    @staticmethod
    def get_current_date():
        """Current date in Indian Standard Time."""
        return datetime.now(ZoneInfo("Asia/Kolkata")).date()

    @staticmethod
    def parse_expiry_date(expiry):
        """Convert DD-MM-YYYY into a date object."""
        return datetime.strptime(
            expiry, "%d-%m-%Y"
        ).date()

    def get_available_expiries(self, response):
        """Extract, parse, and sort available expiries."""
        expiry_data = response.get("data", {}).get(
            "expiryData", []
        )

        expiries = []

        for item in expiry_data:
            try:
                expiry_date = self.parse_expiry_date(
                    item["date"]
                )

                expiries.append({
                    "date": item["date"],
                    "expiry_date": expiry_date,
                    "timestamp": str(item["expiry"]),
                    "expiry_flag": item.get("expiry_flag")
                })

            except (KeyError, TypeError, ValueError):
                logger.warning(
                    f"Skipping invalid expiry record: {item}"
                )

        expiries.sort(key=lambda item: item["expiry_date"])

        return expiries

    def select_expiry(self, expiries):
        """
        Select the nearest upcoming expiry.

        If it is 5 calendar days away or less,
        select the next available expiry instead.
        """
        today = self.get_current_date()

        upcoming = [
            item for item in expiries
            if item["expiry_date"] >= today
        ]

        if not upcoming:
            raise ValueError(
                "No upcoming expiries are available."
            )

        nearest = upcoming[0]

        days_remaining = (
            nearest["expiry_date"] - today
        ).days

        if days_remaining <= self.EXPIRY_THRESHOLD_DAYS:

            if len(upcoming) < 2:
                raise ValueError(
                    f"Nearest expiry is {nearest['date']} "
                    f"({days_remaining} calendar days away), "
                    "but no later expiry is available."
                )

            selected = upcoming[1]

        else:
            selected = nearest

        return selected, days_remaining

    def get_option_chain_data(
        self,
        symbol: str,
        strike_count: int = 10
    ):
        """
        Fetch option chain, select expiry automatically,
        and filter PUTs by delta.
        """

        # Step 1: Request available expiries.
        initial_payload = {
            "symbol": symbol,
            "strikecount": strike_count,
            "timestamp": "",
            "greeks": "1"
        }

        initial_response = self.fyers.optionchain(
            data=initial_payload
        )

        if initial_response.get("s") != "ok":
            logger.error(
                f"Initial option-chain request failed: "
                f"{initial_response}"
            )
            return pd.DataFrame()

        # Step 2: Extract and display expiry dates.
        expiries = self.get_available_expiries(
            initial_response
        )

        if not expiries:
            logger.error("No expiry data returned by Fyers.")
            return pd.DataFrame()

        today = self.get_current_date()

        print(f"\nCurrent date (IST): {today}")
        print("\nAvailable expiries:")

        for item in expiries:
            days = (item["expiry_date"] - today).days

            status = (
                "Expired" if days < 0
                else f"{days} calendar days remaining"
            )

            print(
                f"  {item['date']} | "
                f"Timestamp: {item['timestamp']} | {status}"
            )

        # Step 3: Select expiry using approved rules.
        try:
            selected_expiry, nearest_days = (
                self.select_expiry(expiries)
            )

        except ValueError as exc:
            logger.error(str(exc))
            print(f"\nExpiry selection failed: {exc}")
            return pd.DataFrame()

        print("\nSelected expiry:", selected_expiry["date"])

        if nearest_days <= self.EXPIRY_THRESHOLD_DAYS:
            print(
                f"Nearest expiry was within "
                f"{self.EXPIRY_THRESHOLD_DAYS} days. "
                "Selected the next available expiry."
            )

        # Step 4: Fetch the selected expiry's option chain.
        selected_payload = {
            "symbol": symbol,
            "strikecount": strike_count,
            "timestamp": selected_expiry["timestamp"],
            "greeks": "1"
        }

        response = self.fyers.optionchain(
            data=selected_payload
        )

        if response.get("s") != "ok":
            logger.error(
                f"Selected-expiry request failed: {response}"
            )
            return pd.DataFrame()

        options = response.get(
            "data", {}
        ).get("optionsChain", [])

        # Step 5: Filter PUTs by delta.
        selected_puts = []

        for option in options:

            if option.get("option_type") != "PE":
                continue

            greeks = option.get("greeks") or {}
            delta = greeks.get("delta")

            if delta is None:
                continue

            try:
                delta = float(delta)
            except (TypeError, ValueError):
                continue

            if not (
                self.DELTA_MIN <= delta <= self.DELTA_MAX
            ):
                continue

            selected_puts.append({
                "symbol": option.get("symbol"),
                "expiry": selected_expiry["date"],
                "expiry_timestamp": selected_expiry["timestamp"],
                "strike_price": option.get("strike_price"),
                "ltp": option.get("ltp"),
                "bid": option.get("bid"),
                "ask": option.get("ask"),
                "delta": delta,
                "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"),
                "vega": greeks.get("vega"),
                "iv": greeks.get("iv"),
                "oi": option.get("oi"),
                "volume": option.get("volume")
            })

        columns = [
            "symbol",
            "expiry",
            "expiry_timestamp",
            "strike_price",
            "ltp",
            "bid",
            "ask",
            "delta",
            "gamma",
            "theta",
            "vega",
            "iv",
            "oi",
            "volume"
        ]

        result = pd.DataFrame(
            selected_puts,
            columns=columns
        )

        if result.empty:
            print(
                "\nNo PUT options found for expiry "
                f"{selected_expiry['date']} with delta "
                f"between {self.DELTA_MIN} and "
                f"{self.DELTA_MAX}."
            )
            return result

        # Closest to target delta -0.375 appears first.
        result["_delta_distance"] = (
            result["delta"] - (-0.375)
        ).abs()

        result = (
            result.sort_values("_delta_distance")
            .drop(columns="_delta_distance")
            .reset_index(drop=True)
        )

        print("\nMatching PUT options:\n")
        print(result.to_string(index=False))

        return result


if __name__ == "__main__":

    downloader = DataRetrieval()

    puts = downloader.get_option_chain_data(
        symbol="NSE:SBIN-EQ",
        strike_count=10
    )
