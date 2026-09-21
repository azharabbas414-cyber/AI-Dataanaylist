
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestRegressor


def detect_datetime_columns(df):
    """
    Identify columns that can reasonably be interpreted as dates.
    """

    datetime_columns = []

    for column in df.columns:

        if pd.api.types.is_datetime64_any_dtype(df[column]):
            datetime_columns.append(column)
            continue

        if df[column].dtype == "object":
            converted = pd.to_datetime(
                df[column],
                errors="coerce"
            )

            valid_ratio = converted.notna().mean()

            if valid_ratio >= 0.80:
                datetime_columns.append(column)

    return datetime_columns


def prepare_time_series(df, date_column, value_column):
    """
    Prepare a clean time-series dataset.
    """

    data = df[[date_column, value_column]].copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce"
    )

    data[value_column] = pd.to_numeric(
        data[value_column],
        errors="coerce"
    )

    data = data.dropna()

    data = data.sort_values(date_column)

    data = data.groupby(
        date_column,
        as_index=False
    )[value_column].mean()

    return data


def create_features(data, date_column, value_column):
    """
    Create time-based and lag features.
    """

    result = data.copy()

    result["year"] = result[date_column].dt.year
    result["month"] = result[date_column].dt.month
    result["day"] = result[date_column].dt.day
    result["day_of_week"] = result[date_column].dt.dayofweek
    result["day_of_year"] = result[date_column].dt.dayofyear

    result["trend"] = np.arange(len(result))

    result["lag_1"] = result[value_column].shift(1)
    result["lag_2"] = result[value_column].shift(2)
    result["lag_3"] = result[value_column].shift(3)

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


def build_forecast(
    df,
    date_column,
    value_column,
    forecast_periods=7
):
    """
    Train a Random Forest forecasting model
    and generate future predictions.
    """

    data = prepare_time_series(
        df,
        date_column,
        value_column
    )

    if len(data) < 15:
        raise ValueError(
            "At least 15 valid time-series observations "
            "are required for forecasting."
        )

    featured = create_features(
        data,
        date_column,
        value_column
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

    X = training_data[feature_columns]
    y = training_data[value_column]

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        min_samples_leaf=2,
    )

    model.fit(X, y)

    history = data.copy()

    predictions = []

    last_date = history[date_column].max()

    values = list(history[value_column])

    for step in range(1, forecast_periods + 1):

        future_date = last_date + pd.Timedelta(days=step)

        trend_value = len(history) + step - 1

        lag_1 = values[-1]

        lag_2 = values[-2] if len(values) >= 2 else values[-1]

        lag_3 = values[-3] if len(values) >= 3 else values[-1]

        rolling_3 = np.mean(
            values[-3:]
        )

        rolling_7 = np.mean(
            values[-7:]
        )

        future_features = pd.DataFrame(
            [{
                "year": future_date.year,
                "month": future_date.month,
                "day": future_date.day,
                "day_of_week": future_date.dayofweek,
                "day_of_year": future_date.dayofyear,
                "trend": trend_value,
                "lag_1": lag_1,
                "lag_2": lag_2,
                "lag_3": lag_3,
                "rolling_mean_3": rolling_3,
                "rolling_mean_7": rolling_7,
            }]
        )

        prediction = model.predict(
            future_features[
                feature_columns
            ]
        )[0]

        predictions.append(
            {
                date_column: future_date,
                "Forecast": float(prediction),
            }
        )

        values.append(float(prediction))

    forecast_df = pd.DataFrame(predictions)

    historical = data.rename(
        columns={
            value_column: "Actual"
        }
    )

    return historical, forecast_df, model


def calculate_model_accuracy(
    df,
    date_column,
    value_column
):
    """
    Perform a simple chronological holdout evaluation.
    """

    data = prepare_time_series(
        df,
        date_column,
        value_column
    )

    if len(data) < 20:
        return None

    featured = create_features(
        data,
        date_column,
        value_column
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

    if len(training_data) < 15:
        return None

    split_index = int(
        len(training_data) * 0.8
    )

    train = training_data.iloc[:split_index]
    test = training_data.iloc[split_index:]

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
        train[value_column]
    )

    predictions = model.predict(
        test[feature_columns]
    )

    actual = test[value_column].values

    mae = np.mean(
        np.abs(actual - predictions)
    )

    rmse = np.sqrt(
        np.mean(
            (actual - predictions) ** 2
        )
    )

    non_zero = actual != 0

    if non_zero.any():
        mape = np.mean(
            np.abs(
                (
                    actual[non_zero]
                    - predictions[non_zero]
                )
                / actual[non_zero]
            )
        ) * 100
    else:
        mape = None

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "MAPE": float(mape) if mape is not None else None,
    }
