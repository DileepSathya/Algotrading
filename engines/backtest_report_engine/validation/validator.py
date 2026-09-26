class ReportValidator:

    REQUIRED_COLUMNS = {
        "entry_date",
        "exit_date",
        "entry",
        "exit_price",
        "pnl",
        "pnl_percent",
        "exit_reason",
    }

    @classmethod
    def validate(
        cls,
        df,
        capital
    ):
        ...