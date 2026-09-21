import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestRegressor


# =========================================================
# DATE DETECTION
# =========================================================

def _parse_date_series(series):
    """
    Try to convert a column into datetime using
    several common real-world date formats.
    """

    # Already datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    # Numeric date formats such as:
    # 20230115
    # 202301
    if pd.api.types.is_numeric_dtype(series):

        numeric = series.dropna()

        if numeric.empty:
            return pd.to_datetime(
                series,
                errors="coerce"
            )

        # YYYYMMDD
        values_as_text = (
            numeric.astype("Int64")
            .astype(str)
        )

        if (
            values_as_text.str.len().eq(8).mean()
            >= 0.80
        ):

            parsed = pd.to_datetime(
                series.astype("Int64").astype(str),
                format="%Y%m%d",
                errors="coerce",
            )

            if parsed.notna().mean() >= 0.70:
                return parsed

        # YYYYMM
        if (
            values_as_text.str.len().eq(6).mean()
            >= 0.80
        ):

            parsed = pd.to_datetime(
                series.astype("Int64").astype(str),
                format="%Y%m",
                errors="coerce",
            )

            if parsed.notna().mean() >= 0.70:
                return parsed

    # Standard parsing
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


def detect_datetime_columns(df):
    """
    Automatically detect columns containing
    date/time information.

    Handles:
    - datetime columns
    - date strings
    - timestamps
    - YYYYMMDD
    - YYYYMM
    - columns with date/time-related names
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
    ]

    for column in df.columns:

        series = df[column]

        column_name = str(column).lower()

        parsed = _parse_date_series(series)

        valid_ratio = (
            parsed.notna().mean()
            if len(parsed) > 0
            else 0
        )

        # Strong automatic date detection
        if valid_ratio >= 0.70:

            # Avoid treating ordinary small integers
            # as dates unless the column name indicates time.
            if pd.api.types.is_numeric_dtype(series):

                if any(
                    keyword in column_name
                    for keyword in date_keywords
                ):

                    datetime_columns.append(column)

                else:

                    numeric_values = series.dropna()

                    if not numeric_values.empty:

                        minimum = numeric_values.min()
                        maximum = numeric_values.max()

                        # Reasonable year/date range
                        if (
                            maximum >= 19000101
                            and maximum <= 21001231
                        ):
                            datetime_columns.append(
                                column
                            )

            else:

                datetime_columns.append(column)

            continue

        # Column name strongly suggests date/time.
        # Include it if at least some values can parse.
        if any(
            keyword in column_name
            for keyword in date_keywords
        ):

            if valid_ratio >= 0.30:
                datetime_columns.append(column)

    return list(
        dict.fromkeys(datetime_columns)
    )


# =========================================================
# PREPARE TIME SERIES
# =========================================================

def prepare_time_series(
    df,
    date_column,
    value_column,
):

    data = df[
        [
            date_column,
            value_column,
        ]
    ].copy()

    data[date_column] = _parse_date_series(
        data[date_column]
    )

    data[value_column] = pd.to_numeric(
        data[value_column],
        errors="coerce",
    )

    data = data.dropna(
        subset=[
            date_column,
            value_column,
        ]
    )

    data = data.sort_values(
        date_column
    )

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
# FORECAST MODEL
# =========================================================

def build_forecast(
    df,
    date_column,
    value_column,
    forecast_periods=7,
):

    data = prepare_time_series(
        df,
        date_column,
        value_column,
    )

    if len(data) < 15:

        raise ValueError(
            "At least 15 valid time-series observations "
            "are required for forecasting."
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

    training_data = featured.dropna().copy()

    if len(training_data) < 10:

        raise ValueError(
            "Not enough complete observations after "
            "creating forecasting features."
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

    # Determine the normal time interval
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

    if median_interval <= pd.Timedelta(0):

        median_interval = pd.Timedelta(
            days=1
        )

    predictions = []

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
        len(training_data) * 0.8
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
            actual - predictions
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
