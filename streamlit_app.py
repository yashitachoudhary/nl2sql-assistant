"""NL2SQL Analytics Assistant: ask your database questions in plain English."""
import logging
import numbers
import os

import pandas as pd
import streamlit as st

from app.db.connection import (
    create_db_engine,
    execute_query,
    get_table_names,
    test_connection,
)
from app.models.db_config import DBConfig
from app.services.insight_service import generate_insight
from app.services.llm_service import generate_sql
from app.services.schema_builder import MAX_TABLES, build_schema
from chart_service import build_chart, detect_chart_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Must be the first Streamlit call
st.set_page_config(
    page_title="NL2SQL Analytics Assistant", page_icon="📊", layout="wide"
)

# ── Constants ────────────────────────────────────────────────────────────────
DEMO_DB_PATH = "demo/demo_database.db"
MAX_QUESTIONS = 25      # per session, protects the shared Groq key
MAX_INSIGHT_ROWS = 50   # rows sent to the LLM for insights

# Business rules the LLM cannot guess from column names
DEMO_CONTEXT = """
- users.status: 1 = active, 0 = inactive
- connections.status: 0 = pending, 1 = accepted, 2 = rejected
- messages.is_read: 1 = read, 0 = unread
- sessions.duration_minutes is the session length in minutes
- Daily active users (DAU) = COUNT(DISTINCT sessions.user_id) for sessions starting that day
- revenue.mrr is monthly recurring revenue; revenue.month looks like 'YYYY-MM'
- revenue has 18 monthly rows starting 2025-01
"""

DEMO_QUESTIONS = [
    "How many users signed up each month?",
    "What is the daily active user count for the last 7 days?",
    "Show revenue by month",
    "How many connections are accepted, pending and rejected?",
    "How many posts were created per post type?",
    "What is the average session duration in minutes?",
]

def inject_css() -> None:
    st.markdown("""
    <style>
    /* ── Google Font ─────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ── Global reset ────────────────────────────────────────────── */
    html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #111827;
    font-size: 18px !important;
}

/* Scale up all text elements */
p, li, span, div {
    font-size: 1rem !important;
}
.stChatMessage p {
    font-size: 1.1rem !important;
    line-height: 1.6 !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 1.1rem !important;
}
[data-testid="stSidebar"] button {
    font-size: 1rem !important;
}
h1 {
    font-size: 1.8rem !important;
}
h2, h3 {
    font-size: 1.2rem !important;
}

    /* Force sidebar open by default */
    [data-testid="stSidebar"] {
    min-width: 260px !important;
    transform: none !important;
    }
    [data-testid="collapsedControl"] {
    display: none !important;
    }

    /* ── Hide default Streamlit chrome ───────────────────────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* ── Main background ─────────────────────────────────────────── */
    .stApp {
        background-color: #FFFFFF;
    }

    /* ── Sidebar ─────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
    background-color: #F4F4F1 !important;
    border-right: 1px solid #E5E7EB;
}
[data-testid="stSidebar"] * {
    color: #111827 !important;
}
[data-testid="stSidebar"] .stButton button {
    background-color: white !important;
    border: 1px solid #E5E7EB !important;
    color: #111827 !important;
    text-align: left;
    padding: 6px 10px;
    font-size: 0.85rem;
    width: 100%;
    border-radius: 6px;
    font-family: 'Inter', sans-serif;
    margin-bottom: 4px;
}
[data-testid="stSidebar"] .stButton button:hover {
    background-color: #EFF6FF !important;
    color: #2563EB !important;
    border-color: #2563EB !important;
}
    }
    [data-testid="stSidebar"] .stButton button {
        background-color: transparent;
        border: none;
        color: #111827;
        text-align: left;
        padding: 6px 10px;
        font-size: 0.85rem;
        width: 100%;
        border-radius: 6px;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #EFF6FF;
        color: #2563EB;
    }

    /* ── Primary buttons ─────────────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background-color: #2563EB;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: background-color 0.2s ease;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1D4ED8;
    }

    /* ── Secondary buttons ───────────────────────────────────────── */
    .stButton > button:not([kind="primary"]) {
        background-color: white;
        color: #374151;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
    }
    .stButton > button:not([kind="primary"]):hover {
        border-color: #2563EB;
        color: #2563EB;
    }

    /* ── Chat messages ───────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        background-color: #FAFAFA;
        border: 1px solid #F3F4F6;
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 8px;
    }

    /* ── Input bar ───────────────────────────────────────────────── */
    [data-testid="stChatInput"] textarea {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
    }

    /* ── Metric cards ────────────────────────────────────────────── */
    [data-testid="stMetric"] {
        background-color: #F8FAFF;
        border: 1px solid #DBEAFE;
        border-radius: 10px;
        padding: 16px 20px;
    }
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #2563EB;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        color: #6B7280;
        font-weight: 500;
        text-transform: none;
        font-family: 'Inter', sans-serif;
    }

    /* ── Info boxes (insights) ───────────────────────────────────── */
    .stAlert {
        background-color: #F0F9FF;
        border: 1px solid #BAE6FD;
        border-left: 4px solid #2563EB;
        border-radius: 8px;
        color: #0C4A6E;
        font-family: 'Inter', sans-serif;
    }

    /* ── Dataframe ───────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Expander (SQL view) ─────────────────────────────────────── */
    [data-testid="stExpander"] {
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        background-color: #FAFAFA;
    }

    /* ── Form inputs ─────────────────────────────────────────────── */
    .stTextInput input, .stSelectbox select {
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        font-family: 'Inter', sans-serif;
        background-color: #FAFAFA;
    }
    .stTextInput input:focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
    }

    /* ── Divider ─────────────────────────────────────────────────── */
    hr {
        border: none;
        border-top: 1px solid #E5E7EB;
        margin: 16px 0;
    }

    /* ── Section headers ─────────────────────────────────────────── */
    h1 {
        font-size: 1.4rem;
        font-weight: 700;
        color: #111827;
        font-family: 'Inter', sans-serif;
    }
    h2, h3 {
        font-size: 1rem;
        font-weight: 600;
        color: #374151;
        font-family: 'Inter', sans-serif;
    }

    /* ── Connected status badge ──────────────────────────────────── */
    .connected-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #DCFCE7;
        color: #15803D;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
    }

    /* ── Welcome cards ───────────────────────────────────────────── */
    .welcome-card {
        background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFF 100%);
        border: 1px solid #DBEAFE;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        cursor: pointer;
        transition: box-shadow 0.2s ease;
    }
    .welcome-card:hover {
        box-shadow: 0 4px 12px rgba(37,99,235,0.1);
    }
    .welcome-card h3 {
        color: #2563EB;
        font-size: 0.9rem;
        margin: 0 0 6px 0;
    }
    .welcome-card p {
        color: #6B7280;
        font-size: 0.8rem;
        margin: 0;
    }

    /* ── Navbar ──────────────────────────────────────────────────── */
    .navbar {
        background-color: #1C1C1E;
        padding: 12px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .navbar-brand {
        color: white;
        font-size: 1.1rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.3px;
    }
    .navbar-brand span {
        color: #60A5FA;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────────────
def init_state() -> None:
    """Create per-visitor state on first load."""
    if "stage" not in st.session_state:
        st.session_state.stage = "connect"   # connect -> select -> chat
        st.session_state.engine = None
        st.session_state.dialect = ""
        st.session_state.tables = []
        st.session_state.schema = ""
        st.session_state.is_demo = False
        st.session_state.messages = []
        st.session_state.question_count = 0
        st.session_state.use_insights = True


def disconnect() -> None:
    """Close the connection and wipe everything for this visitor."""
    engine = st.session_state.get("engine")
    if engine is not None:
        engine.dispose()
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def clear_chat() -> None:
    st.session_state.messages = []


# ── Connection logic ─────────────────────────────────────────────────────────
def connect(config: DBConfig, is_demo: bool) -> None:
    """Build an engine, verify it works, and store it for this session."""
    engine = create_db_engine(config)
    try:
        test_connection(engine)
        tables = get_table_names(engine)
    except Exception:
        engine.dispose()
        raise
    st.session_state.engine = engine
    st.session_state.dialect = engine.dialect.name
    st.session_state.tables = tables
    st.session_state.is_demo = is_demo
    # Insights send result rows to Groq: on for the demo, off for real data
    st.session_state.use_insights = is_demo
    st.session_state.stage = "select"


def finish_setup(selected: list[str], context: str) -> None:
    """Build the schema text for the LLM and open the chat screen."""
    st.session_state.schema = build_schema(
        st.session_state.engine,
        selected_tables=selected,
        business_context=context,
    )
    st.session_state.stage = "chat"


# ── Result rendering ─────────────────────────────────────────────────────────
def format_value(value) -> str:
    """Format a number for a metric card."""
    if isinstance(value, numbers.Integral):
        return f"{int(value):,}"
    if isinstance(value, numbers.Real):
        return f"{float(value):,.2f}"
    return str(value)


def prepare_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Rows to DataFrame, converting number-like columns (e.g. MySQL Decimal)."""
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass  # genuinely text, leave it alone
    return df


def render_result(item: dict, key: str) -> None:
    """Draw one answer: metric/chart/table, insight, then the SQL."""
    df = prepare_dataframe(item["results"])

    if df.empty:
        st.info("The query ran but returned no rows.")
    else:
        chart_type = detect_chart_type(df)
        if chart_type == "metric":
            st.metric(
                label=str(df.columns[0]).replace("_", " ").title(),
                value=format_value(df.iloc[0, 0]),
            )
        elif chart_type == "metric_row":
            cols = st.columns(len(df.columns))
            for i, name in enumerate(df.columns):
                cols[i].metric(
                    label=str(name).replace("_", " ").title(),
                    value=format_value(df.iloc[0, i]),
                )
        else:
            fig = build_chart(df, item["question"])
            if fig:
                st.plotly_chart(fig, use_container_width=True, key=key)
            st.dataframe(df, use_container_width=True)

    if item.get("insight"):
        st.markdown("**What this means**")
        st.info(item["insight"])

    with st.expander("View generated SQL"):
        st.code(item["sql"], language="sql")


def render_item(item: dict, key: str) -> None:
    if item["type"] == "text":
        st.markdown(item["content"])
    elif item["type"] == "error":
        st.warning(item["content"])
    else:
        render_result(item, key)


# ── Answering questions ──────────────────────────────────────────────────────
def error_item(message: str) -> dict:
    return {"role": "assistant", "type": "error", "content": message}


def answer_question(question: str) -> dict:
    """Question -> SQL -> rows -> insight. Returns a chat item, never raises."""
    if st.session_state.question_count >= MAX_QUESTIONS:
        return error_item(
            f"You've reached the {MAX_QUESTIONS}-question limit for this "
            "session. Disconnect to start a new one."
        )
    st.session_state.question_count += 1

    try:
        sql = generate_sql(
            question, st.session_state.schema, st.session_state.dialect
        )
        results = execute_query(st.session_state.engine, sql)
    except ValueError as e:
        # Expected failures: unanswerable question or unsafe SQL
        return error_item(str(e))
    except Exception as e:
        logger.error(f"Answering failed: {e}")
        return error_item(
            "I couldn't answer that. Try rephrasing the question."
        )

    insight = ""
    if st.session_state.use_insights and results:
        insight = generate_insight(question, sql, results[:MAX_INSIGHT_ROWS])

    return {
        "role": "assistant",
        "type": "result",
        "question": question,
        "sql": sql,
        "results": results,
        "insight": insight,
    }


def handle_question(question: str) -> None:
    messages = st.session_state.messages
    messages.append({"role": "user", "type": "text", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            item = answer_question(question)
        messages.append(item)
        render_item(item, key=f"chart_{len(messages) - 1}")


# ── Screen 1: connect ────────────────────────────────────────────────────────
def handle_connect_form(
    db_label: str, host: str, port: str, user: str, password: str, name: str
) -> None:
    if not name.strip():
        st.error("Please enter the database name.")
        return
    try:
        config = DBConfig(
            db_type=db_label.lower(),
            db_host=host.strip() or None,
            db_port=int(port) if port.strip() else None,
            db_user=user.strip() or None,
            db_password=password or None,
            db_name=name.strip(),
        )
    except ValueError:  # pydantic's ValidationError is a ValueError
        st.error("Please fill in host and username. Port must be a number.")
        return

    try:
        with st.spinner("Connecting..."):
            connect(config, is_demo=False)
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        st.error(
            "Could not connect. Check the host, port and credentials, and "
            "make sure the server accepts outside connections."
        )
        return
    st.rerun()


def show_connect_screen() -> None:
    # Navbar
    st.markdown("""
    <div class="navbar">
        <div class="navbar-brand">NL2SQL <span>Analytics</span></div>
        <div style="color:#9CA3AF;font-size:0.8rem;font-family:Inter,sans-serif;">
            Ask your database anything
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<h1 style='text-align:center;margin-bottom:4px;'>"
            "📊 NL2SQL Analytics Assistant</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#6B7280;font-size:0.95rem;"
            "margin-bottom:24px;font-family:Inter,sans-serif;'>"
            "Skip the analyst ticket queue. Ask your database a question "
            "and get a chart and insight in seconds.</p>",
            unsafe_allow_html=True,
        )

        # Welcome cards
        st.markdown("""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;">
            <div class="welcome-card">
                <h3>📈 Track Growth</h3>
                <p>Monthly signups, revenue trends, and user activity over time</p>
            </div>
            <div class="welcome-card">
                <h3>👥 Understand Users</h3>
                <p>Active users, session behavior, and account breakdowns</p>
            </div>
            <div class="welcome-card">
                <h3>🔗 Measure Engagement</h3>
                <p>Connections made, messages sent, posts created</p>
            </div>
            <div class="welcome-card">
                <h3>⚡ Instant Insights</h3>
                <p>AI explains what the numbers mean in plain English</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Try it instantly")
        if st.button(
            "🚀 Try the demo database",
            type="primary",
            use_container_width=True,
        ):
            if not os.path.exists(DEMO_DB_PATH):
                st.error(
                    "Demo database not found. Run demo/create_demo_db.py."
                )
            else:
                try:
                    with st.spinner("Loading demo..."):
                        connect(
                            DBConfig(
                                db_type="sqlite", db_name=DEMO_DB_PATH
                            ),
                            is_demo=True,
                        )
                        finish_setup(
                            st.session_state.tables, DEMO_CONTEXT
                        )
                except Exception as e:
                    logger.error(f"Demo setup failed: {e}")
                    st.error("Could not load the demo database.")
                else:
                    st.rerun()

        st.divider()
        st.markdown("#### Connect your own database")
        st.caption(
            "🔒 Credentials stay in this session's memory only — "
            "never saved. Use a **read-only** database user."
        )

        with st.form("connect_form"):
            db_label = st.selectbox(
                "Database type", ["MySQL", "PostgreSQL"]
            )
            c1, c2 = st.columns([3, 1])
            host = c1.text_input("Host", placeholder="db.example.com")
            port = c2.text_input("Port", placeholder="default")
            user = st.text_input("Username")
            password = st.text_input("Password", type="password")
            name = st.text_input("Database name")
            submitted = st.form_submit_button(
                "Connect →", use_container_width=True
            )

        if submitted:
            handle_connect_form(
                db_label, host, port, user, password, name
            )

# ── Screen 2: select tables ──────────────────────────────────────────────────
def show_select_screen() -> None:
    st.title("Choose what the assistant can see")
    tables = st.session_state.tables
    st.caption(
        f"Connected to {st.session_state.dialect}. Found {len(tables)} tables."
    )

    selected = st.multiselect(
        "Tables to include",
        options=tables,
        default=tables if len(tables) <= MAX_TABLES else [],
        help=f"Pick up to {MAX_TABLES}. Fewer tables means better answers.",
    )
    context = st.text_area(
        "Business context (optional)",
        placeholder="e.g. orders.status: 1 = paid, 2 = refunded",
        help="Explain what coded values mean. This noticeably improves accuracy.",
    )

    c1, c2 = st.columns(2)
    if c1.button("Start chatting", type="primary", disabled=not selected):
        try:
            finish_setup(selected, context)
        except ValueError as e:
            st.error(str(e))
            return
        st.rerun()
    c2.button("Back", on_click=disconnect)


# ── Screen 3: chat ───────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        st.header("📊 NL2SQL Assistant")
        if st.session_state.is_demo:
            st.caption("Mode: demo database (SQLite)")
        else:
            st.caption(f"Mode: your {st.session_state.dialect} database")

        st.toggle(
            "AI-written insights",
            key="use_insights",
            help=(
                "When on, up to 50 result rows are sent to the Groq API to "
                "write the explanation. Table and column names are always "
                "sent; row data is not, unless this is on."
            ),
        )
        st.caption(
            f"Questions used: {st.session_state.question_count}/{MAX_QUESTIONS}"
        )

        st.divider()
        st.subheader("💡 Try asking")
        if st.session_state.is_demo:
            for q in DEMO_QUESTIONS:
                if st.button(q, key=f"example_{q}", use_container_width=True):
                    st.session_state.pending_question = q
        else:
            st.markdown(
                "- How many records are in each table?\n"
                "- Show monthly counts for the last year\n"
                "- What are the top 10 by total?"
            )

        st.divider()
        st.button("Clear chat", on_click=clear_chat)
        st.button("Disconnect", on_click=disconnect)


def show_chat_screen() -> None:
    render_sidebar()

    # Navbar with connected status
    dialect = st.session_state.dialect.upper()
    mode = "Demo" if st.session_state.is_demo else "Your DB"
    st.markdown(f"""
    <div class="navbar">
        <div class="navbar-brand">NL2SQL <span>Analytics</span></div>
        <div class="connected-badge">
            🟢 Connected · {dialect} · {mode}
        </div>
    </div>
    """, unsafe_allow_html=True)

    messages = st.session_state.messages
    if not messages:
        st.markdown(
            "<p style='color:#6B7280;font-size:0.9rem;"
            "font-family:Inter,sans-serif;'>"
            "Ask a question below, or pick an example from the sidebar."
            "</p>",
            unsafe_allow_html=True,
        )

    for i, item in enumerate(messages):
        with st.chat_message(item["role"]):
            render_item(item, key=f"chart_{i}")

    typed = st.chat_input(
        "e.g. How many users signed up each month?"
    )
    pending = st.session_state.pop("pending_question", None)
    question = typed or pending
    if question:
        handle_question(question)

# ── Router ───────────────────────────────────────────────────────────────────
init_state()
inject_css()  
stage = st.session_state.stage
if stage == "connect":
    show_connect_screen()
elif stage == "select":
    show_select_screen()
else:
    show_chat_screen()