import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(
    page_title="OmniRouter Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
<style>
    /* Global Typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Title Styling */
    h1 {
        font-weight: 800 !important;
        background: -webkit-linear-gradient(45deg, #25D366, #128C7E);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding-bottom: 10px;
    }

    /* Metric Cards Styling */
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 20px 25px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px rgba(0, 0, 0, 0.2);
        border-color: #25D366;
    }
    div[data-testid="metric-container"] > div {
        align-items: center;
        justify-content: center;
    }
    div[data-testid="metric-container"] label {
        color: #888;
        font-weight: 600;
        font-size: 14px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    
    /* DataFrame Styling */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Subheaders */
    h3 {
        font-weight: 600 !important;
        color: #E0E0E0 !important;
        margin-top: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.title("OmniRouter Intelligence Command Center")
st.markdown("<p style='color: #888; font-size: 16px; margin-top: -15px;'>Real-time performance telemetry and automated routing analytics</p>", unsafe_allow_html=True)

# --- Sidebar & Data Loading ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg", width=60)
    st.markdown("## ⚙️ Dashboard Controls")
    
    auto_refresh = st.checkbox("Enable Auto-Refresh (5s)", value=True)
    st.markdown("---")
    
    st.markdown("### 📅 Date Filter")
    days_to_show = st.slider("Past Days to Analyze", 1, 30, 7)
    
    st.markdown("---")
    st.markdown("<p style='font-size: 12px; color: #666;'>OmniRouter Enterprise v1.0.0</p>", unsafe_allow_html=True)

# Dynamic TTL based on toggle
ttl_val = 5 if auto_refresh else 3600

@st.cache_data(ttl=ttl_val)
def load_data(days):
    try:
        conn = sqlite3.connect("analytics.db")
        # Fetch data within the time window
        query = f"SELECT * FROM interaction_metrics WHERE timestamp >= datetime('now', '-{days} days')"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except sqlite3.OperationalError:
        return pd.DataFrame()

df = load_data(days_to_show)

# --- Main Dashboard Layout ---
if df.empty:
    st.info("📊 **Awaiting Telemetry...** No data found for the selected time range. Send a message to the webhook to generate analytics.")
else:
    # --- KPI Row ---
    total_messages = len(df)
    total_tokens = df["tokens_used"].sum()
    avg_latency = df["latency_ms"].mean()
    escalations = df["escalated"].sum()
    escalation_rate = (escalations / total_messages) * 100 if total_messages > 0 else 0
    fallbacks = df["used_fallback"].sum()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("⚡ Total Interactions", f"{total_messages:,}")
    kpi2.metric("⏱️ Avg Routing Latency", f"{avg_latency:,.0f} ms")
    kpi3.metric("🧠 Total LLM Tokens", f"{total_tokens:,}")
    kpi4.metric("👥 Human Handoff Rate", f"{escalation_rate:.1f}%", f"{escalations} sessions" if escalations > 0 else "Optimal", delta_color="inverse")

    # --- Analytics Charts Row ---
    st.markdown("### 📈 Interaction Telemetry")
    chart_col1, chart_col2 = st.columns([6, 4])

    with chart_col1:
        # Beautiful Spline Line Chart for Latency
        df_sorted = df.sort_values("timestamp")
        fig_latency = px.line(
            df_sorted, 
            x="timestamp", 
            y="latency_ms", 
            template="plotly_dark",
            color_discrete_sequence=["#25D366"]
        )
        fig_latency.update_traces(line_shape='spline', fill='tozeroy', fillcolor='rgba(37, 211, 102, 0.1)', line=dict(width=3))
        fig_latency.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="",
            yaxis_title="Latency (ms)",
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='#333', zeroline=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig_latency, use_container_width=True)

    with chart_col2:
        # Elegant Donut Chart for Intents
        if 'intent' in df.columns:
            intent_counts = df["intent"].fillna("Unknown").value_counts().reset_index()
            intent_counts.columns = ["Intent", "Count"]
            fig_intents = px.pie(
                intent_counts, 
                values="Count", 
                names="Intent",
                hole=0.6,
                template="plotly_dark",
                color_discrete_sequence=px.colors.sequential.Tealgrn
            )
            fig_intents.update_layout(
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            # Add a center text
            fig_intents.add_annotation(text=f"<b>{len(intent_counts)}</b><br>Intents", x=0.5, y=0.5, font_size=20, showarrow=False)
            st.plotly_chart(fig_intents, use_container_width=True)

    # --- Recent Logs Row ---
    st.markdown("### 📋 Live Routing Ledger")
    
    # Prettify the dataframe before displaying
    display_df = df.sort_values("timestamp", ascending=False).head(100).copy()
    display_df["timestamp"] = display_df["timestamp"].dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df["escalated"] = display_df["escalated"].map({1: "⚠️ Yes", 0: "✅ No", True: "⚠️ Yes", False: "✅ No"})
    display_df["used_fallback"] = display_df["used_fallback"].map({1: "⚠️ Yes", 0: "✅ No", True: "⚠️ Yes", False: "✅ No"})
    
    # Rename columns for presentation
    display_df = display_df.rename(columns={
        "timestamp": "Time",
        "session_id": "Session ID",
        "intent": "Detected Intent",
        "llm_model": "LLM Engine",
        "tokens_used": "Tokens",
        "latency_ms": "Latency (ms)",
        "escalated": "Human Handoff",
        "used_fallback": "Fallback Triggered"
    })
    
    st.dataframe(
        display_df[["Time", "Session ID", "Detected Intent", "LLM Engine", "Latency (ms)", "Human Handoff", "Tokens"]],
        use_container_width=True,
        hide_index=True,
        height=300
    )
