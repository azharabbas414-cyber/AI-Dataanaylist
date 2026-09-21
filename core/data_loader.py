import pandas as pd


def load_uploaded_data(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith('.csv'):
        return pd.read_csv(uploaded_file)
    if name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(uploaded_file)
    raise ValueError('Unsupported file type. Please upload CSV or Excel.')
