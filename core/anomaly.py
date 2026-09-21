import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest


def detect_statistical_anomalies(df):
    """
    Detect anomalies using the IQR method.
    Works independently on each numeric column.
    """

    numeric_columns = list(df.select_dtypes(include="number").columns)

    results = []

    for column in numeric_columns:
        series = df[column]

        valid_series = series.dropna()

        if len(valid_series) < 4:
            continue

        q1 = valid_series.quantile(0.25)
        q3 = valid_series.quantile(0.75)

        iqr = q3 - q1

        if iqr == 0:
            continue

        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        mask = (series < lower_bound) | (series > upper_bound)

        anomaly_count = int(mask.sum())

        if anomaly_count > 0:
            anomaly_percentage = (
                anomaly_count / len(valid_series)
            ) * 100

            results.append(
                {
                    "column": column,
                    "method": "IQR",
                    "anomalies": anomaly_count,
                    "percentage": round(anomaly_percentage, 2),
                    "lower_bound": round(float(lower_bound), 4),
                    "upper_bound": round(float(upper_bound), 4),
                }
            )

    return pd.DataFrame(results)


def detect_isolation_forest_anomalies(df):
    """
    Detect multivariate anomalies using Isolation Forest.

    Only numeric columns are used.
    """

    numeric_df = df.select_dtypes(include="number").copy()

    if numeric_df.empty:
        return pd.DataFrame()

    if len(numeric_df) < 10:
        return pd.DataFrame()

    # Remove columns that contain no usable variation
    usable_columns = []

    for column in numeric_df.columns:
        if numeric_df[column].nunique(dropna=True) > 1:
            usable_columns.append(column)

    numeric_df = numeric_df[usable_columns]

    if numeric_df.empty:
        return pd.DataFrame()

    # Fill missing numeric values using median
    numeric_df = numeric_df.fillna(numeric_df.median())

    if numeric_df.empty:
        return pd.DataFrame()

    contamination = min(
        max(0.01, 0.05),
        0.49
    )

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )

    predictions = model.fit_predict(numeric_df)

    scores = model.decision_function(numeric_df)

    result = df.copy()

    result["_anomaly_prediction"] = predictions
    result["_anomaly_score"] = scores

    result["Anomaly"] = result["_anomaly_prediction"].apply(
        lambda value: "Anomaly" if value == -1 else "Normal"
    )

    result = result.drop(columns=["_anomaly_prediction"])

    result = result.sort_values(
        "_anomaly_score",
        ascending=True
    )

    return result


def anomaly_summary(df):
    """
    Generate a high-level anomaly summary.
    """

    statistical = detect_statistical_anomalies(df)
    isolation = detect_isolation_forest_anomalies(df)

    total_anomalies = 0

    if not isolation.empty and "Anomaly" in isolation.columns:
        total_anomalies = int(
            (isolation["Anomaly"] == "Anomaly").sum()
        )

    total_rows = len(df)

    if total_rows > 0:
        anomaly_percentage = (
            total_anomalies / total_rows
        ) * 100
    else:
        anomaly_percentage = 0

    return {
        "total_rows": total_rows,
        "anomaly_rows": total_anomalies,
        "anomaly_percentage": round(anomaly_percentage, 2),
        "statistical_anomalies": statistical,
        "isolation_results": isolation,
    }


def explain_anomalies(df, anomaly_results, max_rows=20):
    """
    Generate simple explanations for detected anomalous rows.
    """

    if anomaly_results.empty:
        return pd.DataFrame()

    numeric_columns = list(
        df.select_dtypes(include="number").columns
    )

    anomaly_rows = anomaly_results[
        anomaly_results["Anomaly"] == "Anomaly"
    ].head(max_rows)

    explanations = []

    for index, row in anomaly_rows.iterrows():

        reasons = []

        for column in numeric_columns:

            value = row[column]

            if pd.isna(value):
                continue

            series = df[column].dropna()

            if len(series) < 4:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)

            iqr = q3 - q1

            if iqr == 0:
                continue

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            if value < lower:
                reasons.append(
                    f"{column} is unusually low"
                )

            elif value > upper:
                reasons.append(
                    f"{column} is unusually high"
                )

        if reasons:
            explanation = "; ".join(reasons[:3])
        else:
            explanation = (
                "Multivariate pattern differs significantly "
                "from normal observations"
            )

        explanations.append(
            {
                "row_index": index,
                "anomaly_score": round(
                    float(row["_anomaly_score"]),
                    4
                ),
                "explanation": explanation,
            }
        )

    return pd.DataFrame(explanations)
