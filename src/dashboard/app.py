import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

# Configure page
st.set_page_config(
    page_title="OmniRouter Analytics",
    page_icon="🤖",
    layout="wide",
)

st.title("OmniRouter Analytics Dashboard")
st.markdown("Real-time performance metrics and interaction tracking for the highly scalable WhatsApp Orchestrator.")

# Load Data
@st.cache_data(ttl=5) # Refresh every 5 seconds
def load_data():
    try:
        conn = sqlite3.connect("analytics.db")
        df = pd.read_sql_query("SELECT * FROM interaction_metrics", conn)
        conn.close()
        
        # Parse datetime
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        return df
    except sqlite3.OperationalError:
        # DB might not exist yet
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No analytics data found. Interact with the bot to generate metrics.")
else:
    # --- KPIs ---
    total_messages = len(df)
    total_tokens = df["tokens_used"].sum()
    avg_latency = df["latency_ms"].mean()
    
    escalations = df["escalated"].sum()
    escalation_rate = (escalations / total_messages) * 100 if total_messages > 0 else 0
    
    fallbacks = df["used_fallback"].sum()
    fallback_rate = (fallbacks / total_messages) * 100 if total_messages > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Messages", f"{total_messages:,}")
    col2.metric("Total Tokens", f"{total_tokens:,}")
    col3.metric("Avg Latency", f"{avg_latency:,.0f} ms")
    col4.metric("Escalation Rate", f"{escalation_rate:.1f}%")
    col5.metric("Fallback Rate", f"{fallback_rate:.1f}%")

    st.markdown("---")

    # --- Charts ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Latency Over Time")
        # Line chart of latency
        df_sorted = df.sort_values("timestamp")
        fig_latency = px.line(
            df_sorted, 
            x="timestamp", 
            y="latency_ms", 
            title="Message Processing Latency",
            labels={"timestamp": "Time", "latency_ms": "Latency (ms)"},
            template="plotly_dark"
        )
        st.plotly_chart(fig_latency, use_container_width=True)
        
    with chart_col2:
        st.subheader("Intent Distribution")
        # Bar chart of intents
        if 'intent' in df.columns:
            intent_counts = df["intent"].fillna("Unknown").value_counts().reset_index()
            intent_counts.columns = ["Intent", "Count"]
            fig_intents = px.bar(
                intent_counts, 
                x="Intent", 
                y="Count", 
                title="Detected Intents",
                color="Intent",
                template="plotly_dark"
            )
            st.plotly_chart(fig_intents, use_container_width=True)

    st.markdown("---")
    
    # --- Recent Interactions Table ---
    st.subheader("Recent Interactions")
    
    display_df = df.sort_values("timestamp", ascending=False).head(50)
    # Format for display
    display_df = display_df[["timestamp", "session_id", "intent", "llm_model", "tokens_used", "latency_ms", "escalated", "used_fallback"]]
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )
