import os

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

# Configure Streamlit page
st.set_page_config(page_title="Weather App", layout="wide")
st.title("Weather / Rainfall Explorer")

st.markdown(
    """
This app runs inside Databricks Apps and connects to a Unity Catalog table
through a SQL warehouse.

Use it to explore weather / rainfall data.
"""
)

# ---- Change these to your real objects ----
DEFAULT_TABLE = "catalog.schema.weather_table"  # e.g. analytics.weather.daily
WAREHOUSE_HTTP_PATH = os.environ.get("DATABRICKS_WAREHOUSE_HTTP_PATH", "")

cfg = Config()  # works both locally (via profile) and in Databricks Apps

if not WAREHOUSE_HTTP_PATH:
    st.warning(
        "Environment variable `DATABRICKS_WAREHOUSE_HTTP_PATH` is not set.\n\n"
        "Set this in the Databricks App settings after deployment."
    )

table_name = st.text_input("Unity Catalog table", value=DEFAULT_TABLE)
row_limit = st.slider("Row limit", min_value=100, max_value=20_000, value=1_000, step=100)


# ---- Databricks helpers ----
@st.cache_resource
def get_connection(http_path: str):
    if not http_path:
        raise RuntimeError("HTTP path for SQL warehouse is empty.")
    return sql.connect(
        server_hostname=cfg.host,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
    )


@st.cache_data(show_spinner=True)
def load_table(table: str, limit: int) -> pd.DataFrame:
    conn = get_connection(WAREHOUSE_HTTP_PATH)
    with conn.cursor() as cursor:
        query = f"SELECT * FROM {table} LIMIT {limit}"
        cursor.execute(query)
        return cursor.fetchall_arrow().to_pandas()


# ---- UI logic ----
if WAREHOUSE_HTTP_PATH and table_name:
    try:
        df = load_table(table_name, row_limit)

        st.subheader("Data preview")
        st.dataframe(df)

        # Basic weather-specific helpers
        date_cols = [c for c in df.columns if "date" in c.lower()]
        numeric_cols = df.select_dtypes(include="number").columns.tolist()

        # Pick a date column, if present
        if date_cols:
            date_col = st.selectbox("Date column", options=date_cols)
            df[date_col] = pd.to_datetime(df[date_col])

            with st.expander("Filter by date range", expanded=False):
                min_date = df[date_col].min()
                max_date = df[date_col].max()
                start, end = st.date_input(
                    "Date range",
                    value=(min_date.date(), max_date.date()),
                    min_value=min_date.date(),
                    max_value=max_date.date(),
                )
                mask = (df[date_col] >= pd.to_datetime(start)) & (
                    df[date_col] <= pd.to_datetime(end)
                )
                df = df[mask]

        st.subheader("Summary stats")
        st.write(df.describe(include="all"))

        if numeric_cols:
            metric_col = st.selectbox(
                "Numeric column to chart (e.g. rainfall amount)",
                options=numeric_cols,
            )
            st.subheader(f"Time series of `{metric_col}`")
            if date_cols:
                st.line_chart(df.set_index(date_cols[0])[metric_col])
            else:
                st.line_chart(df[metric_col])

    except Exception as e:
        st.error(f"Error querying table: {e}")
else:
    st.stop()
