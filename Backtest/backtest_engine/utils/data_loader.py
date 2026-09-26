import json

import pandas as pd


class HistoricalDataLoader:
    """
    Loads historical market data for backtesting.
    """

    REQUIRED_COLUMNS = {
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    @staticmethod
    def load_json(path: str) -> pd.DataFrame:
        """
        Load historical data from a JSON file.

        Parameters
        ----------
        path : str
            Path to historical JSON data.

        Returns
        -------
        pd.DataFrame
            Historical OHLCV data.
        """

        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        df = pd.DataFrame(data)

        HistoricalDataLoader._validate_columns(df)

        df["date"] = pd.to_datetime(df["date"])

        df = (
            df
            .sort_values(["symbol", "date"])
            .reset_index(drop=True)
        )

        return df

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        """
        Validate that required OHLCV columns exist.
        """

        missing_columns = (
            HistoricalDataLoader.REQUIRED_COLUMNS
            - set(df.columns)
        )

        if missing_columns:
            raise ValueError(
                "Historical data is missing required columns: "
                f"{sorted(missing_columns)}"
            )