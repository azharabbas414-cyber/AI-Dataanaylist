import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestRegressor


# =========================================================
# SAFE DATE PARSING
# =========================================================

def _parse_date_series(series):
    """
    Safely convert a pandas Series into datetime.

    Supports:
    - datetime columns
    - normal date strings
    - timestamps
    - YYYY-MM-DD
    - DD/MM/YYYY
    - MM/DD/YYYY
    - YYYYMMDD
    - YYYYMM

    Numeric columns that are clearly not dates are
    ignored safely.
    """

    # -----------------------------------------------------
    # Already datetime
    # -----------------------------------------------------

    if pd.api.types.is_datetime64_any_dtype(series):

        return pd.to_datetime(
            series,
            errors="coerce",
        )

    # -----------------------------------------------------
    # Numeric columns
    # -----------------------------------------------------

    if pd.api.types.is_numeric_dtype(series):

        numeric = pd.to_numeric(
            series,
            errors="coerce",
        )

        numeric = numeric.dropna()

        if numeric.empty:

            return pd.Series(
                pd.NaT,
                index=series.index,
                dtype="datetime64[ns]",
            )

        # Check whether values are integer-like.
        # Do NOT cast directly to Int64 because a numeric
        # column may contain decimal values.
        integer_like = (
            np.isfinite(numeric)
            & np.isclose(
                numeric,
                np.round(numeric),
            )
        )

        if integer_like.mean() < 0.80:

            return pd.Series(
                pd.NaT,
                index=series.index,
                dtype="datetime64[ns]",
            )

        integer_values = numeric[
            integer_like
        ].round().astype("int64")

        text_values = integer_values.astype(str)

        # -------------------------------------------------
        # YYYYMMDD
        # -------------------------------------------------

        eight_digit = (
            text_values.str.len() == 8
        )

        if eight_digit.mean() >= 0.70:

            parsed = pd.to_datetime(
                integer_values.astype(str),
                format="%Y%m%d",
                errors="coerce",
            )

            if parsed.notna().mean() >= 0.70:

                result = pd.Series(
                    pd.NaT,
                    index=series.index,
                    dtype="datetime64[ns]",
                )

                result.loc[
                    integer_values.index
                ] = parsed

                return result

        # -------------------------------------------------
        # YYYYMM
        # -------------------------------------------------

        six_digit = (
            text_values.str.len() == 6
        )

        if six_digit.mean() >= 0.70:

            parsed = pd.to_datetime(
                integer_values.astype(str),
                format="%Y%m",
                errors="coerce",
            )

            if parsed.notna().mean() >= 0.70:

                result = pd.Series(
                    pd.NaT,
                    index=series.index,
                    dtype="datetime64[ns]",
                )

                result.loc[
                    integer_values.index
                ] = parsed

                return result

        # Not a date-like numeric column.
        return pd.Series(
            pd.NaT,
            index=series.index,
            dtype="datetime64[ns]",
        )

    # -----------------------------------------------------
    # Text / object columns
    # -----------------------------------------------------

    try:

        parsed = pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
        )

    except Exception:

        parsed = pd.to_datetime(
            series,
            errors="coerce",
        )

    return parsed


# =========================================================
# DATE COLUMN DETECTION
# =========================================================

def detect_datetime_columns(df):
    """
    Detect columns that contain date/time information.
    """

    datetime_columns = []

    date_keywords = [
        "date",
        "time",
        "timestamp",
        "datetime",
        "month",
        "year",
        "day",
        "period",
        "created",
        "updated",
        "start",
        "end",
    ]

    for column in df.columns:

        series = df[column]

        column_name = str(
            column
        ).strip().lower()

        parsed = _parse_date_series(
            series
        )

        if len(parsed) == 0:
            continue

        valid_ratio = (
            parsed.notna().mean()
        )

        # -------------------------------------------------
        # Strong date detection
        # -------------------------------------------------

        if valid_ratio >= 0.70:

            # Numeric columns need stronger evidence
            # because ordinary numbers can otherwise
            # be mistaken for dates.
            if pd.api.types.is_numeric_dtype(
                series
            ):

                if any(
                    keyword in column_name
                    for keyword in date_keywords
                ):

                    datetime_columns.append(
                        column
                    )

            else:

                datetime_columns.append(
                    column
                )

            continue

        # -------------------------------------------------
        # Column name indicates date/time
        # -------------------------------------------------

        if any(
            keyword in column_name
            for keyword in date_keywords
        ):

            if valid_ratio >= 0.30:

                datetime_columns.append(
                    column
                )

    return list(
        dict.fromkeys(
            datetime_columns
        )
    )


# =========================================================
# PREPARE TIME SERIES
# =========================================================

def prepare_time_series(
    df,
    date_column,
    value_column,
):
    """
    Prepare a clean time-series dataframe.
    """

    if date_column not in df.columns:

        raise ValueError(
            f"Date column '{date_column}' "
            "was not found."
        )

    if value_column not in df.columns:

        raise ValueError(
            f"Value column '{value_column}' "
            "was not found."
        )

    data = df[
        [
            date_column,
            value_column,
        ]
    ].copy()

    # Parse date
    data[date_column] = (
        _parse_date_series(
            data[date_column]
        )
    )

    # Convert value to numeric
    data[value_column] = pd.to_numeric(
        data[value_column],
        errors="coerce",
    )

    # Remove invalid observations
    data = data.dropna(
        subset=[
            date_column,
            value_column,
        ]
    )

    if data.empty:

        raise ValueError(
            "No valid date/value observations "
            "were found."
        )

    # Sort chronologically
    data = data.sort_values(
        date_column
    )

    # If multiple measurements exist on the
    # same date, use the average.
    data = data.groupby(
        date_column,
        as_index=False,
    )[value_column].mean()

    return data


# =========================================================
# FEATURE ENGINEERING
# =========================================================

def create_features(
    data,
    date_column,
    value_column,
):
    """
    Create machine-learning features from
    the time series.
    """

    result = data.copy()

    result["year"] = (
        result[date_column].dt.year
    )

    result["month"] = (
        result[date_column].dt.month
    )

    result["day"] = (
        result[date_column].dt.day
    )

    result["day_of_week"] = (
        result[date_column].dt.dayofweek
    )

    result["day_of_year"] = (
        result[date_column].dt.dayofyear
    )

    result["trend"] = np.arange(
        len(result)
    )

    result["lag_1"] = (
        result[value_column].shift(1)
    )

    result["lag_2"] = (
        result[value_column].shift(2)
    )

    result["lag_3"] = (
        result[value_column].shift(3)
    )

    result["rolling_mean_3"] = (
        result[value_column]
        .rolling(3)
        .mean()
    )

    result["rolling_mean_7"] = (
        result[value_column]
        .rolling(7)
        .mean()
    )

    return result


# =========================================================
# BUILD FORECAST
# =========================================================

def build_forecast(
    df,
    date_column,
    value_column,
    forecast_periods=7,
):
    """
    Train forecasting model and generate
    future predictions.
    """

    data = prepare_time_series(
        df,
        date_column,
        value_column,
    )

    if len(data) < 15:

        raise ValueError(
            "At least 15 valid time-series "
            "observations are required."
        )

    featured = create_features(
        data,
        date_column,
        value_column,
    )

    feature_columns = [
        "year",
        "month",
        "day",
        "day_of_week",
        "day_of_year",
        "trend",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_mean_7",
    ]

    training_data = (
        featured
        .dropna()
        .copy()
    )

    if len(training_data) < 10:

        raise ValueError(
            "Not enough complete observations "
            "after feature creation."
        )

    X = training_data[
        feature_columns
    ]

    y = training_data[
        value_column
    ]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )

    model.fit(
        X,
        y,
    )

    values = list(
        data[value_column]
    )

    last_date = data[
        date_column
    ].max()

    # -----------------------------------------------------
    # Detect normal time interval
    # -----------------------------------------------------

    date_differences = (
        data[date_column]
        .diff()
        .dropna()
    )

    if not date_differences.empty:

        median_interval = (
            date_differences.median()
        )

    else:

        median_interval = pd.Timedelta(
            days=1
        )

    if (
        pd.isna(median_interval)
        or median_interval
        <= pd.Timedelta(0)
    ):

        median_interval = pd.Timedelta(
            days=1
        )

    predictions = []

    # -----------------------------------------------------
    # Generate future values
    # -----------------------------------------------------

    for step in range(
        1,
        forecast_periods + 1,
    ):

        future_date = (
            last_date
            + median_interval * step
        )

        trend_value = (
            len(data)
            + step
            - 1
        )

        lag_1 = values[-1]

        lag_2 = (
            values[-2]
            if len(values) >= 2
            else values[-1]
        )

        lag_3 = (
            values[-3]
            if len(values) >= 3
            else values[-1]
        )

        rolling_3 = np.mean(
            values[-3:]
        )

        rolling_7 = np.mean(
            values[-7:]
        )

        future_features = pd.DataFrame(
            [
                {
                    "year": future_date.year,
                    "month": future_date.month,
                    "day": future_date.day,
                    "day_of_week": (
                        future_date.dayofweek
                    ),
                    "day_of_year": (
                        future_date.dayofyear
                    ),
                    "trend": trend_value,
                    "lag_1": lag_1,
                    "lag_2": lag_2,
                    "lag_3": lag_3,
                    "rolling_mean_3": rolling_3,
                    "rolling_mean_7": rolling_7,
                }
            ]
        )

        prediction = model.predict(
            future_features[
                feature_columns
            ]
        )[0]

        predictions.append(
            {
                date_column: future_date,
                "Forecast": float(
                    prediction
                ),
            }
        )

        values.append(
            float(prediction)
        )

    forecast_df = pd.DataFrame(
        predictions
    )

    historical = data.rename(
        columns={
            value_column: "Actual"
        }
    )

    return (
        historical,
        forecast_df,
        model,
    )


# =========================================================
# MODEL ACCURACY
# =========================================================

def calculate_model_accuracy(
    df,
    date_column,
    value_column,
):
    """
    Calculate basic hold-out forecasting accuracy.
    """

    data = prepare_time_series(
        df,
        date_column,
        value_column,
    )

    if len(data) < 20:
        return None

    featured = create_features(
        data,
        date_column,
        value_column,
    )

    feature_columns = [
        "year",
        "month",
        "day",
        "day_of_week",
        "day_of_year",
        "trend",
        "lag_1",
        "lag_2",
        "lag_3",
        "rolling_mean_3",
        "rolling_mean_7",
    ]

    training_data = (
        featured
        .dropna()
        .copy()
    )

    if len(training_data) < 15:
        return None

    split_index = int(
        len(training_data) * 0.80
    )

    train = training_data.iloc[
        :split_index
    ]

    test = training_data.iloc[
        split_index:
    ]

    if test.empty:
        return None

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )

    model.fit(
        train[feature_columns],
        train[value_column],
    )

    predictions = model.predict(
        test[feature_columns]
    )

    actual = (
        test[value_column]
        .values
    )

    mae = np.mean(
        np.abs(
            actual
            - predictions
        )
    )

    rmse = np.sqrt(
        np.mean(
            (
                actual
                - predictions
            ) ** 2
        )
    )

    non_zero = actual != 0

    if non_zero.any():

        mape = (
            np.mean(
                np.abs(
                    (
                        actual[non_zero]
                        - predictions[non_zero]
                    )
                    / actual[non_zero]
                )
            )
            * 100
        )

    else:

        mape = None

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "MAPE": (
            float(mape)
            if mape is not None
            else None
        ),
    }
