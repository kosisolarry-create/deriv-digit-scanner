import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from collections import Counter
import json
import time
from websocket import create_connection
from datetime import datetime

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="MATRIX Digit Scanner Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #e0e0e0; }
    .signal-box {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border: 1px solid #22c55e55;
        border-radius: 16px;
        padding: 22px;
        text-align: center;
    }
    .signal-text {
        font-size: 2.1rem;
        font-weight: 800;
        color: #22c55e;
        margin: 0;
    }
    .confidence-text {
        font-size: 1.5rem;
        color: #fbbf24;
        margin-top: 6px;
    }
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        border: 1px solid #334155;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 600;
        margin-top: 10px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Markets
# -----------------------------
MARKETS = {
    "Volatility 10": "R_10",
    "Volatility 25": "R_25",
    "Volatility 50": "R_50",
    "Volatility 75": "R_75",
    "Volatility 100": "R_100",
    "Volatility 10 (1s)": "1HZ10V",
    "Volatility 25 (1s)": "1HZ25V",
    "Volatility 50 (1s)": "1HZ50V",
    "Volatility 75 (1s)": "1HZ75V",
    "Volatility 100 (1s)": "1HZ100V",
}

# -----------------------------
# Deriv API
# -----------------------------
def get_ticks_history(symbol: str, count: int = 100):
    try:
        ws = create_connection(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            timeout=12
        )
        request = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "ticks"
        }
        ws.send(json.dumps(request))
        result = json.loads(ws.recv())
        ws.close()

        if "history" in result and "prices" in result["history"]:
            return result["history"]["prices"]
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def extract_last_digits(prices):
    digits = []
    for p in prices:
        s = f"{float(p):.2f}"
        digit = int(s.split(".")[0][-1])
        digits.append(digit)
    return digits


def analyze_digits(digits):
    if not digits or len(digits) < 10:
        return None

    counter = Counter(digits)
    total = len(digits)
    freq = {d: (counter.get(d, 0) / total) * 100 for d in range(10)}

    sorted_freq = sorted(freq.items(), key=lambda x: x[1])
    coldest = sorted_freq[0]
    hottest = sorted_freq[-1]

    even_count = sum(counter.get(d, 0) for d in [0, 2, 4, 6, 8])
    even_pct = (even_count / total) * 100
    odd_pct = 100 - even_pct

    over_count = sum(counter.get(d, 0) for d in [5, 6, 7, 8, 9])
    over_pct = (over_count / total) * 100
    under_pct = 100 - over_pct

    max_dev = max(abs(f - 10) for f in freq.values())
    confidence = min(97.5, round(50 + max_dev * 4.2, 1))

    return {
        "freq": freq,
        "coldest": coldest,
        "hottest": hottest,
        "even_pct": even_pct,
        "odd_pct": odd_pct,
        "over_pct": over_pct,
        "under_pct": under_pct,
        "confidence": confidence,
        "sample_size": total,
        "last_digit": digits[-1],
        "digits": digits
    }


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("⚙️ MATRIX Settings")

market_name = st.sidebar.selectbox("Market", list(MARKETS.keys()), index=4)
symbol = MARKETS[market_name]

tick_count = st.sidebar.select_slider("Ticks to analyze", [50, 75, 100, 150, 200], value=100)

mode = st.sidebar.radio(
    "Signal Mode",
    ["Matches / Differs", "Even / Odd", "Over / Under"],
    index=0
)

auto_refresh = st.sidebar.checkbox("Auto-refresh every 5s", value=True)
scan_btn = st.sidebar.button("🔄 Run Deep Scan", use_container_width=True, type="primary")

st.sidebar.markdown("---")
st.sidebar.warning(
    "Statistical analysis only.\n"
    "Volatility Indices are randomly generated.\n"
    "No strategy guarantees profit. Trade responsibly."
)

# -----------------------------
# Session State
# -----------------------------
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "history" not in st.session_state:
    st.session_state.history = []
if "trades" not in st.session_state:
    st.session_state.trades = []          # Win/Loss tracker
if "last_update" not in st.session_state:
    st.session_state.last_update = None

# -----------------------------
# Main Title
# -----------------------------
st.title("📡 MATRIX Digit Scanner Pro")
st.caption("Matches • Differs • Martingale • Target Profit • Win/Loss Tracker")

# Fetch data
if scan_btn or auto_refresh or st.session_state.analysis is None:
    with st.spinner(f"Scanning {market_name}..."):
        prices = get_ticks_history(symbol, tick_count)
        if prices:
            digits = extract_last_digits(prices)
            analysis = analyze_digits(digits)
            st.session_state.analysis = analysis
            st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

            if analysis:
                if mode == "Matches / Differs":
                    signal = f"MATCHES {analysis['coldest'][0]}"
                elif mode == "Even / Odd":
                    signal = "EVEN" if analysis["even_pct"] < 48 else "ODD"
                else:
                    signal = "UNDER" if analysis["under_pct"] < 48 else "OVER"

                st.session_state.history.insert(0, {
                    "Time": st.session_state.last_update,
                    "Market": market_name,
                    "Signal": signal,
                    "Confidence": analysis["confidence"],
                    "Last Digit": analysis["last_digit"]
                })
                st.session_state.history = st.session_state.history[:12]

analysis = st.session_state.analysis

if analysis:
    # ===== LIVE SIGNAL =====
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown("### 🎯 Live Signal")

        if mode == "Matches / Differs":
            main_signal = f"MATCHES {analysis['coldest'][0]}"
            alt = f"Alt: DIFFERS {analysis['hottest'][0]}"
        elif mode == "Even / Odd":
            main_signal = "EVEN" if analysis["even_pct"] < 48 else "ODD"
            alt = f"Even {analysis['even_pct']:.1f}% | Odd {analysis['odd_pct']:.1f}%"
        else:
            main_signal = "UNDER 5" if analysis["under_pct"] < 48 else "OVER 5"
            alt = f"Under {analysis['under_pct']:.1f}% | Over {analysis['over_pct']:.1f}%"

        st.markdown(f"""
        <div class="signal-box">
            <p class="signal-text">{main_signal}</p>
            <p class="confidence-text">{analysis['confidence']}% Confidence</p>
            <p style="color:#94a3b8; margin-top:6px;">{alt}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("### 📊 Market Info")
        st.metric("Market", market_name)
        st.metric("Last Digit", analysis["last_digit"])
        st.metric("Ticks Analyzed", analysis["sample_size"])
        st.caption(f"Updated: {st.session_state.last_update}")

    st.markdown("---")

    # ===== MARTINGALE + TARGET PROFIT =====
    st.markdown('<p class="section-title">📈 Martingale & Target Profit</p>', unsafe_allow_html=True)

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        base_stake = st.number_input("Base Stake ($)", min_value=0.35, value=1.00, step=0.35)
    with col_b:
        multiplier = st.number_input("Multiplier", min_value=1.5, value=2.0, step=0.1)
    with col_c:
        max_steps = st.number_input("Max Steps", min_value=3, value=6, step=1)
    with col_d:
        martingale_type = st.selectbox("Type", ["Classic Martingale", "Anti-Martingale"])

    # Target Profit Calculator
    st.markdown("#### 🎯 Target Profit Calculator")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        target_profit = st.number_input("Target Profit ($)", min_value=1.0, value=10.0, step=1.0)
    with col_t2:
        payout_rate = st.number_input("Payout Rate (e.g. 0.95)", min_value=0.5, value=0.95, step=0.01)
    with col_t3:
        win_rate_needed = st.number_input("Assumed Win Rate %", min_value=40.0, value=55.0, step=1.0)

    # Calculate required wins roughly
    avg_win = base_stake * payout_rate
    wins_needed = int(np.ceil(target_profit / avg_win)) if avg_win > 0 else 0

    st.info(f"To reach **${target_profit:.2f}** profit you need approximately **{wins_needed}** winning trades "
            f"(at ${base_stake} stake & {payout_rate*100:.0f}% payout).")

    # Martingale Progression
    progression = []
    stake = base_stake
    cumulative = 0.0

    for i in range(int(max_steps)):
        cumulative += stake
        progression.append({
            "Step": i + 1,
            "Stake": round(stake, 2),
            "Cumulative Risk": round(cumulative, 2)
        })
        if martingale_type == "Classic Martingale":
            stake *= multiplier          # increase after loss
        else:
            stake = base_stake           # Anti keeps base or you can customize

    st.dataframe(pd.DataFrame(progression), use_container_width=True, hide_index=True)
    st.caption(f"Total risk after {max_steps} consecutive losses: **${cumulative:.2f}**")

    st.markdown("---")

    # ===== WIN / LOSS TRACKER =====
    st.markdown('<p class="section-title">📝 Simple Win / Loss Tracker</p>', unsafe_allow_html=True)

    col_w1, col_w2, col_w3 = st.columns([1, 1, 2])
    with col_w1:
        if st.button("✅ Register WIN", use_container_width=True):
            st.session_state.trades.append({"Result": "WIN", "Time": datetime.now().strftime("%H:%M:%S")})
    with col_w2:
        if st.button("❌ Register LOSS", use_container_width=True):
            st.session_state.trades.append({"Result": "LOSS", "Time": datetime.now().strftime("%H:%M:%S")})

    if st.session_state.trades:
        trades_df = pd.DataFrame(st.session_state.trades)
        wins = len(trades_df[trades_df["Result"] == "WIN"])
        losses = len(trades_df[trades_df["Result"] == "LOSS"])
        total = wins + losses
        winrate = (wins / total * 100) if total > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Wins", wins)
        c2.metric("Losses", losses)
        c3.metric("Total Trades", total)
        c4.metric("Win Rate", f"{winrate:.1f}%")

        with st.expander("Trade Log"):
            st.dataframe(trades_df.iloc[::-1], use_container_width=True, hide_index=True)

        if st.button("Clear Tracker"):
            st.session_state.trades = []
            st.rerun()
    else:
        st.info("No trades registered yet. Use the buttons above after each trade.")

    st.markdown("---")

    # ===== FREQUENCY CHART =====
    st.subheader("Digit Frequency Distribution")
    freq_df = pd.DataFrame({
        "Digit": list(analysis["freq"].keys()),
        "Frequency %": list(analysis["freq"].values())
    })
    fig = px.bar(freq_df, x="Digit", y="Frequency %", color="Frequency %",
                 color_continuous_scale="teal", text_auto=".1f")
    fig.update_layout(template="plotly_dark", height=360, margin=dict(t=20, b=20), xaxis=dict(dtick=1))
    fig.add_hline(y=10, line_dash="dash", line_color="#64748b", annotation_text="Expected 10%")
    st.plotly_chart(fig, use_container_width=True)

    # ===== HOT / COLD CARDS =====
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#60a5fa">❄️ Coldest</div>
            <h2>{analysis['coldest'][0]}</h2>
            <small>{analysis['coldest'][1]:.1f}%</small>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#f87171">🔥 Hottest</div>
            <h2>{analysis['hottest'][0]}</h2>
            <small>{analysis['hottest'][1]:.1f}%</small>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div>Even / Odd</div>
            <h3>{analysis['even_pct']:.1f}% / {analysis['odd_pct']:.1f}%</h3>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div>Under / Over</div>
            <h3>{analysis['under_pct']:.1f}% / {analysis['over_pct']:.1f}%</h3>
        </div>
        """, unsafe_allow_html=True)

    # ===== SIGNAL HISTORY =====
    st.markdown("---")
    st.subheader("📜 Signal History")
    if st.session_state.history:
        st.dataframe(pd.DataFrame(st.session_state.history), use_container_width=True, hide_index=True)
    else:
        st.info("No signals yet.")

    with st.expander("Last 40 digits"):
        st.code("  ".join(map(str, analysis["digits"][-40:])))

else:
    st.info("Click **Run Deep Scan** to begin analysis.")

# Auto refresh
if auto_refresh and analysis:
    time.sleep(5)
    st.rerun()
