
import pandas as pd
import numpy as np


# =========================================================
# COLUMN CLASSIFICATION
# =========================================================

def classify_columns(df):

    numeric_columns = list(
        df.select_dtypes(include="number").columns
    )

    categorical_columns = list(
        df.select_dtypes(
            include=["object", "category", "bool"]
        ).columns
    )

    datetime_columns = list(
        df.select_dtypes(
            include=["datetime", "datetimetz"]
        ).columns
    )

    return {
        "numeric": numeric_columns,
        "categorical": categorical_columns,
        "datetime": datetime_columns,
    }


# =========================================================
# DATASET HEALTH
# =========================================================

def dataset_health(df):

    rows = len(df)
    columns = len(df.columns)

    total_cells = rows * columns

    missing_cells = int(
        df.isna().sum().sum()
    )

    duplicate_rows = int(
        df.duplicated().sum()
    )

    if total_cells > 0:

        completeness = (
            1 - missing_cells / total_cells
        ) * 100

    else:

        completeness = 0

    if rows > 0:

        duplicate_percentage = (
            duplicate_rows / rows
        ) * 100

    else:

        duplicate_percentage = 0

    # Simple quality score

    score = 100

    score -= min(
        completeness,
        20
    ) if completeness < 100 else 0

    score -= min(
        duplicate_percentage,
        10
    )

    score = max(
        0,
        min(100, score)
    )

    return {
        "rows": rows,
        "columns": columns,
        "missing_values": missing_cells,
        "duplicate_rows": duplicate_rows,
        "completeness": round(
            completeness,
            2
        ),
        "duplicate_percentage": round(
            duplicate_percentage,
            2
        ),
        "quality_score": round(
            score,
            1
        ),
    }


# =========================================================
# NUMERIC SUMMARY
# =========================================================

def numeric_summary(df):

    numeric_df = df.select_dtypes(
        include="number"
    )

    if numeric_df.empty:
        return pd.DataFrame()

    summary = numeric_df.describe().T

    summary["median"] = (
        numeric_df.median()
    )

    summary["missing"] = (
        numeric_df.isna().sum()
    )

    summary["unique"] = (
        numeric_df.nunique()
    )

    summary = summary[
        [
            "count",
            "mean",
            "median",
            "std",
            "min",
            "25%",
            "50%",
            "75%",
            "max",
            "missing",
            "unique",
        ]
    ]

    return summary


# =========================================================
# CATEGORICAL SUMMARY
# =========================================================

def categorical_summary(df):

    categorical_columns = list(
        df.select_dtypes(
            include=[
                "object",
                "category",
                "bool",
            ]
        ).columns
    )

    results = []

    for column in categorical_columns:

        series = df[column]

        results.append(
            {
                "column": column,
                "unique_values": int(
                    series.nunique(
                        dropna=True
                    )
                ),
                "missing": int(
                    series.isna().sum()
                ),
                "top_value": (
                    series.mode().iloc[0]
                    if not series.mode().empty
                    else None
                ),
                "top_value_count": int(
                    series.value_counts(
                        dropna=True
                    ).iloc[0]
                )
                if not series.value_counts(
                    dropna=True
                ).empty
                else 0,
            }
        )

    return pd.DataFrame(results)


# =========================================================
# OUTLIER DETECTION
# =========================================================

def detect_outliers(df):

    numeric_columns = list(
        df.select_dtypes(
            include="number"
        ).columns
    )

    results = []

    for column in numeric_columns:

        series = df[column].dropna()

        if len(series) < 4:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

        iqr = q3 - q1

        if iqr == 0:
            outlier_count = 0

        else:

            lower_bound = (
                q1 - 1.5 * iqr
            )

            upper_bound = (
                q3 + 1.5 * iqr
            )

            outlier_count = int(
                (
                    (series < lower_bound)
                    |
                    (series > upper_bound)
                ).sum()
            )

        percentage = (
            outlier_count / len(series)
        ) * 100

        results.append(
            {
                "column": column,
                "outliers": outlier_count,
                "outlier_percentage": round(
                    percentage,
                    2
                ),
            }
        )

    return pd.DataFrame(results)


# =========================================================
# CORRELATION ANALYSIS
# =========================================================

def correlation_pairs(df):

    numeric_df = df.select_dtypes(
        include="number"
    )

    if len(numeric_df.columns) < 2:

        return pd.DataFrame()

    correlation = numeric_df.corr()

    results = []

    columns = list(
        correlation.columns
    )

    for i in range(len(columns)):

        for j in range(i + 1, len(columns)):

            first = columns[i]
            second = columns[j]

            value = correlation.loc[
                first,
                second
            ]

            if pd.isna(value):
                continue

            results.append(
                {
                    "column_1": first,
                    "column_2": second,
                    "correlation": round(
                        float(value),
                        3
                    ),
                    "absolute_correlation": round(
                        abs(float(value)),
                        3
                    ),
                }
            )

    result_df = pd.DataFrame(
        results
    )

    if not result_df.empty:

        result_df = result_df.sort_values(
            "absolute_correlation",
            ascending=False
        )

    return result_df


# =========================================================
# TOP CATEGORIES
# =========================================================

def top_categories(
    df,
    max_columns=5,
    max_values=10
):

    categorical_columns = list(
        df.select_dtypes(
            include=[
                "object",
                "category",
                "bool",
            ]
        ).columns
    )

    results = {}

    for column in categorical_columns[
        :max_columns
    ]:

        counts = (
            df[column]
            .value_counts(
                dropna=False
            )
            .head(max_values)
        )

        results[column] = counts

    return results


# =========================================================
# AUTOMATIC FINDINGS
# =========================================================

def generate_findings(df):

    findings = []

    health = dataset_health(df)

    classifications = classify_columns(df)

    # -----------------------------------------------------
    # Data quality
    # -----------------------------------------------------

    if health["missing_values"] > 0:

        findings.append(
            f"Dataset contains "
            f"{health['missing_values']:,} missing values."
        )

    else:

        findings.append(
            "No missing values were detected."
        )

    if health["duplicate_rows"] > 0:

        findings.append(
            f"{health['duplicate_rows']:,} duplicate "
            f"rows were detected."
        )

    else:

        findings.append(
            "No duplicate rows were detected."
        )

    # -----------------------------------------------------
    # Numeric columns
    # -----------------------------------------------------

    numeric_columns = (
        classifications["numeric"]
    )

    if numeric_columns:

        findings.append(
            f"The dataset contains "
            f"{len(numeric_columns)} numeric "
            f"columns suitable for quantitative analysis."
        )

        numeric_df = df[
            numeric_columns
        ]

        variability = (
            numeric_df.std(
                numeric_only=True
            )
            .sort_values(
                ascending=False
            )
        )

        if not variability.empty:

            highest_variability = (
                variability.index[0]
            )

            findings.append(
                f"'{highest_variability}' has "
                f"the highest standard deviation "
                f"among numeric columns."
            )

    # -----------------------------------------------------
    # Categorical columns
    # -----------------------------------------------------

    categorical_columns = (
        classifications["categorical"]
    )

    if categorical_columns:

        findings.append(
            f"The dataset contains "
            f"{len(categorical_columns)} "
            f"categorical columns."
        )

    # -----------------------------------------------------
    # Outliers
    # -----------------------------------------------------

    outliers = detect_outliers(df)

    if not outliers.empty:

        significant = outliers[
            outliers["outliers"] > 0
        ]

        if not significant.empty:

            highest = significant.sort_values(
                "outlier_percentage",
                ascending=False
            ).iloc[0]

            findings.append(
                f"'{highest['column']}' contains "
                f"{int(highest['outliers']):,} "
                f"potential outliers."
            )

    # -----------------------------------------------------
    # Correlation
    # -----------------------------------------------------

    correlations = correlation_pairs(df)

    if not correlations.empty:

        strongest = correlations.iloc[0]

        if strongest["absolute_correlation"] >= 0.7:

            findings.append(
                f"Strong relationship detected between "
                f"'{strongest['column_1']}' and "
                f"'{strongest['column_2']}' "
                f"(correlation "
                f"{strongest['correlation']})."
            )

    return findings


# =========================================================
# COMPLETE ANALYSIS
# =========================================================

def analyze_dataset(df):

    return {
        "health": dataset_health(df),

        "classification": classify_columns(
            df
        ),

        "numeric_summary": numeric_summary(
            df
        ),

        "categorical_summary": categorical_summary(
            df
        ),

        "outliers": detect_outliers(
            df
        ),

        "correlations": correlation_pairs(
            df
        ),

        "top_categories": top_categories(
            df
        ),

        "findings": generate_findings(
            df
        ),
    }
