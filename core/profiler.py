import pandas as pd


def profile_dataframe(df: pd.DataFrame):
    rows, columns = df.shape
    missing = int(df.isna().sum().sum())
    total = rows * columns
    column_profile = pd.DataFrame({
        'Column': df.columns.astype(str),
        'Data Type': [str(x) for x in df.dtypes],
        'Non-Null': [int(df[c].notna().sum()) for c in df.columns],
        'Missing': [int(df[c].isna().sum()) for c in df.columns],
        'Unique': [int(df[c].nunique(dropna=True)) for c in df.columns],
    })
    return {
        'rows': rows,
        'columns': columns,
        'missing_pct': (missing / total * 100) if total else 0,
        'duplicates': int(df.duplicated().sum()),
        'column_profile': column_profile,
    }
