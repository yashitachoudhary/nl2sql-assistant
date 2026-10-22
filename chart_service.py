import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import logging

logger = logging.getLogger(__name__)

# Keywords that suggest a column contains date/time data
DATE_KEYWORDS = ["date", "day", "week", "month", "year", "time", "_at", "created", "updated"]

# Keywords that suggest a column contains categorical data
CATEGORY_KEYWORDS = ["type", "status", "name", "category", "label", "device", "os", "browser"]


def is_date_column(col_name: str) -> bool:
    """Check if a column name suggests it contains date/time values."""
    col_lower = col_name.lower()
    return any(keyword in col_lower for keyword in DATE_KEYWORDS)


def is_category_column(col_name: str) -> bool:
    """Check if a column name suggests it contains categorical values."""
    col_lower = col_name.lower()
    return any(keyword in col_lower for keyword in CATEGORY_KEYWORDS)


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return list of numeric column names in the dataframe."""
    return df.select_dtypes(include=["number"]).columns.tolist()


def detect_chart_type(df: pd.DataFrame) -> str:
    """
    Analyze the dataframe shape and column names to decide
    what visualization type fits best.

    Returns one of: 'metric', 'line', 'bar', 'table'
    """
    rows, cols = df.shape

    # Single value → metric card
    if rows == 1 and cols == 1:
        return "metric"

    # Single row, multiple columns → metric cards row
    if rows == 1 and cols > 1:
        return "metric_row"

    # Too many columns → just show table
    if cols > 5:
        return "table"

    # Multiple rows → look at column types
    numeric_cols = get_numeric_columns(df)
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    # No numeric columns → table only
    if not numeric_cols:
        return "table"

    # Check if non-numeric column looks like a date → line chart
    if non_numeric_cols:
        if any(is_date_column(col) for col in non_numeric_cols):
            return "line"
        # Non-numeric category column → bar chart
        if any(is_category_column(col) for col in non_numeric_cols):
            return "bar"

    # Default for multiple numeric rows → bar chart
    return "bar"


def build_chart(df: pd.DataFrame, question: str) -> go.Figure | None:
    """
    Build and return a Plotly figure based on the dataframe.
    Returns None if no chart is appropriate.

    Args:
        df: Query result as a dataframe
        question: Original user question (used as chart title)

    Returns:
        Plotly Figure or None
    """
    chart_type = detect_chart_type(df)
    logger.info(f"Detected chart type: {chart_type}")

    numeric_cols = get_numeric_columns(df)
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

    try:
        if chart_type == "metric":
            # Single number — no chart, handled separately in streamlit
            return None

        if chart_type == "metric_row":
            # Multiple single values — no chart, handled separately
            return None

        if chart_type == "table":
            # Too complex — no chart
            return None

        if chart_type == "line":
            x_col = non_numeric_cols[0]
            y_col = numeric_cols[0]
            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                title=question,
                markers=True,       # show dots on data points
                template="plotly_white"
            )
            fig.update_layout(
                xaxis_title=x_col.replace("_", " ").title(),
                yaxis_title=y_col.replace("_", " ").title()
            )
            return fig

        if chart_type == "bar":
            if non_numeric_cols:
                x_col = non_numeric_cols[0]
                y_col = numeric_cols[0]
            else:
                # All numeric — use index as x
                df = df.reset_index()
                x_col = "index"
                y_col = numeric_cols[0]

            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                title=question,
                template="plotly_white",
                text=y_col          # show values on top of bars
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                xaxis_title=x_col.replace("_", " ").title(),
                yaxis_title=y_col.replace("_", " ").title()
            )
            return fig

    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
        return None

    return None