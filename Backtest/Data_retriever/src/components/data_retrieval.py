import os
import json

from pathlib import Path
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

        response = self.fyers.get_profile()

        print(response)

        return response

    def hist_data(self):

        # -----------------------------------------
        # RESOLUTION
        # -----------------------------------------

        resolution = str(
            input(
                "Enter the time frame 1/5/15/30/60/D/W/M: "
            )
        ).strip()

        # -----------------------------------------
        # RETRIEVAL PERIOD
        # -----------------------------------------

        data_retrivel_period = 366

        if resolution in ["1", "5", "15", "30", "60"]:
            data_retrivel_period = 100

        # -----------------------------------------
        # ARTIFACTS DIRECTORY
        # -----------------------------------------

        artifacts_dir = Path(
            r"D:\FM\ALGOTRADING\artifacts\backtest"
        )

        artifacts_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        stem = "hist_data"
        ext = ".json"

        # -----------------------------------------
        # SYMBOLS PER FILE
        # -----------------------------------------

        symbols_per_file = 1

        # -----------------------------------------
        # DATE RANGE
        # -----------------------------------------

        choice = input(
            "Do you want to retrieve custom data? (y/n): "
        ).strip().lower()

        if choice == "y":

            from_str = input(
                "Enter FROM date (YYYY-MM-DD): "
            ).strip()

            to_str = input(
                "Enter TO date (YYYY-MM-DD): "
            ).strip()

            range_from = date.fromisoformat(from_str)
            range_to = date.fromisoformat(to_str)

            if range_from > range_to:
                raise ValueError(
                    f"FROM date {range_from} cannot be "
                    f"after TO date {range_to}."
                )

        else:

            range_to = date.today()

            range_from = (
                range_to -
                timedelta(days=data_retrivel_period)
            )

        # -----------------------------------------
        # SYMBOL LIST
        # -----------------------------------------

        in_symbol_list = (
            config_manager.data_loading_config()
        )

        symbols_list = [
            format_symbol(symbol)
            for symbol in in_symbol_list
        ]

        total_symbol_length = len(symbols_list)

        symbol_count = 0

        # -----------------------------------------
        # DOWNLOAD DATA
        # -----------------------------------------

        for idx, symbol in enumerate(symbols_list):

            if idx % symbols_per_file == 0:

                batch_num = (
                    idx // symbols_per_file
                ) + 1

                file_path = (
                    artifacts_dir /
                    f"{stem}_{resolution}_part{batch_num}{ext}"
                )

                clear_hist_data_json(
                    str(file_path)
                )

                logger.info(
                    f"Batch {batch_num}: "
                    f"saving up to {symbols_per_file} "
                    f"symbols to {file_path}"
                )

            # -------------------------------------
            # DATE CHUNKS
            # -------------------------------------

            chunk_from = range_from

            while chunk_from <= range_to:

                chunk_to = min(
                    chunk_from +
                    timedelta(
                        days=data_retrivel_period - 1
                    ),
                    range_to
                )

                data = {
                    "symbol": symbol,
                    "resolution": resolution,
                    "date_format": "1",
                    "range_from": chunk_from.isoformat(),
                    "range_to": chunk_to.isoformat(),
                    "cont_flag": "1"
                }

                response = self.fyers.history(
                    data=data
                )

                if response.get("s") == "error":

                    logger.error(
                        f"{symbol}: "
                        f"{response.get('message')}"
                    )

                else:

                    data_with_symbols = (
                        extract_candles_with_symbol(
                            response_json=response,
                            symbol=symbol
                        )
                    )

                    if data_with_symbols:

                        save_to_raw_hist_data_json(
                            data_with_symbols,
                            str(file_path)
                        )

                chunk_from = (
                    chunk_to +
                    timedelta(days=1)
                )

                sleep(0.2)

            symbol_count += 1

            print(
                f"{symbol_count}/{total_symbol_length} "
                f"{symbol}"
            )

        logger.info(
            f"Historical data retrieval completed "
            f"for resolution {resolution}"
        )

        # -----------------------------------------
        # COMBINE THE PART FILES
        # -----------------------------------------

        self.combine_data(resolution)

    def combine_data(self, resolution):

        # -----------------------------------------
        # FIXED ARTIFACTS DIRECTORY
        # -----------------------------------------

        artifacts_dir = Path(
            r"D:\FM\ALGOTRADING\artifacts\backtest"
        )

        stem = "hist_data"

        # -----------------------------------------
        # FIND PART FILES
        # -----------------------------------------

        part_files = sorted(
            artifacts_dir.glob(
                f"{stem}_{resolution}_part*.json"
            ),
            key=lambda p: int(
                p.stem.rsplit("part", 1)[-1]
            )
        )

        print(
            f"\nFound {len(part_files)} "
            f"part files for resolution {resolution}"
        )

        if not part_files:

            print(
                f"No files found for resolution "
                f"{resolution}"
            )

            return

        # -----------------------------------------
        # COMBINE
        # -----------------------------------------

        combined = []

        for part_path in part_files:

            with open(
                part_path,
                "r",
                encoding="utf-8"
            ) as f:

                records = json.load(f)

            combined.extend(records)

            print(
                f"{part_path.name}: "
                f"{len(records):,} rows "
                f"(total: {len(combined):,})"
            )

        # -----------------------------------------
        # SAVE COMBINED FILE
        # -----------------------------------------

        output_path = (
            artifacts_dir /
            f"{stem}_{resolution}.json"
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                combined,
                f,
                indent=4
            )

        print(
            f"\nSaved {len(combined):,} rows to:"
        )

        print(output_path)