````markdown
# 📊 AI Data Analyst Assistant

An AI-powered data analysis application built with Python and Streamlit.

## Features

- Upload CSV files
- Upload Excel files
- Dataset preview
- Row and column statistics
- Missing-value detection
- Duplicate-row detection
- Numeric statistical summary
- Basic visualizations
- Ask questions about your dataset
- AI-generated analysis
- Python/Pandas suggestions

## Technology

- Python
- Streamlit
- Pandas
- OpenAI API
- OpenPyXL

## Project Structure

```text
ai-data-analyst/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
└── .streamlit/
    └── secrets.toml.example
````

## Run Locally

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create:

```text
.streamlit/secrets.toml
```

Add:

```toml
OPENAI_API_KEY = "your-api-key"
```

Run:

```bash
streamlit run app.py
```

The application will open in your browser.

## Security

Never commit your API key to GitHub.

The real `secrets.toml` file should remain local.

## Future Features

* Natural-language data analysis
* Automatic chart generation
* Data cleaning
* Anomaly detection
* AI-generated reports
* Multiple dataset support
* Conversation history
* SQL analysis
* Advanced visualization
* RAG/document analysis

```
```
