import collections
import json
import random
import threading
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


# ============================================================
# DERIV DIGIT SCANNER V2
# Educational analysis tool
# ============================================================

st.set_page_config(
    page_title="Deriv Digit Scanner V2",
    page_icon="📊",
    layout="wide"
)

SYMBOLS = [
    "R_10",
    "R_25",
    "R_50",
    "R_75",
    "R_100",
    "R_10_1s",
    "R_25_1s",
    "R_50_1s",
    "R_75_1s",
    "R_100_1s",
]


def get_last_digit(price):
    """
    Extract the final visible digit from a price.
    """
    text = f"{float(price):.10f}".rstrip("0").rstrip(".")

    if "." not in text:
        return int(text[-1])

    return int(text[-1])


def analyse_window(ticks, window):
    """
    Analyse digit frequency in the selected tick window.
    """

    if len(ticks) < window:
        return None

    recent = ticks[-window:]
    digits = [get_last_digit(x) for x in recent]

    counter = collections.Counter(digits)

    results = []

    for digit in range(10):
        count = counter.get(digit, 0)
        percentage = (count / window) * 100
        deviation = percentage - 10

        results.append({
            "digit": digit,
            "count": count,
            "percentage": percentage,
            "deviation": deviation
        })

    hottest = max(results, key=lambda x: x["deviation"])
    coldest = min(results, key=lambda x: x["deviation"])

    even = sum(1 for d in digits if d % 2 == 0)
    odd = window - even

    even_pct = even / window * 100
    odd_pct = odd / window * 100

    over = sum(1 for d in digits if d > 4)
    under = sum(1 for d in digits if d < 5)

    over_pct = over / window * 100
    under_pct = under / window * 100

    return {
        "window": window,
        "digits": digits,
        "frequency": results,
        "hottest": hottest,
        "coldest": coldest,
        "even_pct": even_pct,
        "odd_pct": odd_pct,
        "over_pct": over_pct,
        "under_pct": under_pct
    }


def consensus_score(analyses):
    """
    Creates an experimental scanner score.

    This is NOT a probability of the next digit.
    """

    if not analyses:
        return None

    digit_scores = {d: 0 for d in range(10)}

    weights = {
        50: 1.0,
        100: 1.5,
        200: 2.0
    }

    for window, analysis in analyses.items():

        if not analysis:
            continue

        weight = weights.get(window, 1)

        for row in analysis["frequency"]:
            digit = row["digit"]
            deviation = row["deviation"]

            digit_scores[digit] += deviation * weight

    best_digit = max(
        digit_scores,
        key=digit_scores.get
    )

    worst_digit = min(
        digit_scores,
        key=digit_scores.get
    )

    maximum = max(digit_scores.values())
    minimum = min(digit_scores.values())

    spread = maximum - minimum

    if spread <= 0:
        score = 50
    else:
        score = 50 + min(49, abs(digit_scores[best_digit]) / spread * 49)

    return {
        "digit_scores": digit_scores,
        "best_digit": best_digit,
        "worst_digit": worst_digit,
        "score": round(score)
    }


# ============================================================
# LIVE DERIV COLLECTOR
# ============================================================

class DerivCollector:

    def __init__(self, symbol):
        self.symbol = symbol
        self.ticks = []
        self.running = False
        self.ws = None
        self.lock = threading.Lock()
        self.thread = None

    def on_message(self, ws, message):

        try:
            data = json.loads(message)

            if "tick" in data:

                price = float(
                    data["tick"]["quote"]
                )

                with self.lock:

                    self.ticks.append(price)

                    if len(self.ticks) > 1000:
                        self.ticks = self.ticks[-1000:]

        except Exception:
            pass

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, *args):
        self.running = False

    def on_open(self, ws):

        request = {
            "ticks": self.symbol,
            "subscribe": 1
        }

        ws.send(json.dumps(request))

    def run(self):

        url = (
            "wss://ws.derivws.com/"
            "websockets/v3?app_id=1089"
        )

        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.ws.run_forever(
            ping_interval=20,
            ping_timeout=10
        )

    def start(self):

        if not HAS_WEBSOCKET:
            return False

        if self.running:
            return True

        self.running = True

        self.thread = threading.Thread(
            target=self.run,
            daemon=True
        )

        self.thread.start()

        return True

    def stop(self):

        self.running = False

        if self.ws:

            try:
                self.ws.close()
            except Exception:
                pass

    def get_ticks(self):

        with self.lock:
            return list(self.ticks)


# ============================================================
# SESSION STATE
# ============================================================

if "collector" not in st.session_state:
    st.session_state.collector = None

if "demo_ticks" not in st.session_state:

    base = 1000.0

    st.session_state.demo_ticks = [
        base + random.uniform(-1, 1)
        for _ in range(300)
    ]


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚙️ Scanner Settings")

mode = st.sidebar.radio(
    "Data source",
    [
        "Live Deriv",
        "Demo"
    ]
)

symbol = st.sidebar.selectbox(
    "Market",
    SYMBOLS,
    index=4
)

refresh = st.sidebar.slider(
    "Refresh seconds",
    2,
    15,
    5
)

st.sidebar.markdown("---")

st.sidebar.info(
    "This scanner measures recent digit frequency. "
    "It does NOT guarantee the next digit."
)


# ============================================================
# HEADER
# ============================================================

st.title("📊 Deriv Digit Scanner V2")

st.caption(
    "Live market analysis • Multi-window frequency scanner • "
    "Experimental scoring"
)


# ============================================================
# LIVE CONTROLS
# ============================================================

c1, c2, c3 = st.columns(3)

with c1:

    if st.button(
        "▶️ Start Scanner",
        use_container_width=True
    ):

        if mode == "Live Deriv":

            if st.session_state.collector:
                st.session_state.collector.stop()

            collector = DerivCollector(symbol)

            if collector.start():

                st.session_state.collector = collector

                st.success(
                    f"Connected to {symbol}"
                )

            else:

                st.error(
                    "websocket-client is not installed."
                )

        else:

            st.success(
                "Demo scanner started."
            )


with c2:

    if st.button(
        "⏹ Stop",
        use_container_width=True
    ):

        if st.session_state.collector:

            st.session_state.collector.stop()

            st.session_state.collector = None

        st.info("Scanner stopped.")


with c3:

    auto_refresh = st.checkbox(
        "Auto refresh",
        value=True
    )


# ============================================================
# GET TICKS
# ============================================================

if mode == "Live Deriv":

    if st.session_state.collector:

        ticks = (
            st.session_state
            .collector
            .get_ticks()
        )

    else:

        ticks = []

else:

    last = (
        st.session_state
        .demo_ticks[-1]
    )

    new_price = (
        last +
        random.uniform(-0.05, 0.05)
    )

    st.session_state.demo_ticks.append(
        new_price
    )

    if len(st.session_state.demo_ticks) > 1000:

        st.session_state.demo_ticks = (
            st.session_state.demo_ticks[-1000:]
        )

    ticks = st.session_state.demo_ticks


# ============================================================
# STATUS
# ============================================================

st.markdown("### 📡 Feed Status")

status1, status2, status3 = st.columns(3)

with status1:
    st.metric(
        "Market",
        symbol if mode == "Live Deriv" else "DEMO"
    )

with status2:
    st.metric(
        "Ticks collected",
        len(ticks)
    )

with status3:
    st.metric(
        "Data source",
        mode
    )


if len(ticks) < 50:

    st.warning(
        f"Collecting data... {len(ticks)}/50 ticks"
    )

else:

    # ========================================================
    # MULTI WINDOW ANALYSIS
    # ========================================================

    analyses = {}

    for window in [50, 100, 200]:

        analyses[window] = analyse_window(
            ticks,
            window
        )


    # ========================================================
    # CONSENSUS
    # ========================================================

    consensus = consensus_score(
        analyses
    )

    st.markdown("---")

    st.markdown(
        "## 🎯 Experimental Consensus"
    )

    cc1, cc2, cc3 = st.columns(3)

    with cc1:

        st.metric(
            "Consensus Digit",
            str(consensus["best_digit"])
        )

    with cc2:

        st.metric(
            "Experimental Score",
            f"{consensus['score']}/100"
        )

    with cc3:

        st.metric(
            "Least Frequent",
            str(consensus["worst_digit"])
        )


    st.info(
        "The score measures agreement between recent "
        "frequency samples. It is NOT an 80% prediction "
        "of the next tick."
    )


    # ========================================================
    # WINDOW TABLE
    # ========================================================

    st.markdown("## 📈 Multi-Window Analysis")

    table = []

    for window in [50, 100, 200]:

        result = analyses[window]

        if result:

            table.append({
                "Window": window,
                "Hottest": result["hottest"]["digit"],
                "Hot %": round(
                    result["hottest"]["percentage"],
                    1
                ),
                "Coldest": result["coldest"]["digit"],
                "Cold %": round(
                    result["coldest"]["percentage"],
                    1
                ),
                "Even %": round(
                    result["even_pct"],
                    1
                ),
                "Odd %": round(
                    result["odd_pct"],
                    1
                ),
                "Over %": round(
                    result["over_pct"],
                    1
                ),
                "Under %": round(
                    result["under_pct"],
                    1
                )
            })

    st.dataframe(
        pd.DataFrame(table),
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # DIGIT HEATMAP
    # ========================================================

    st.markdown("## 🔢 Digit Heatmap")

    analysis = analyses[100]

    cols = st.columns(10)

    for row in analysis["frequency"]:

        digit = row["digit"]
        pct = row["percentage"]
        deviation = row["deviation"]

        if deviation >= 6:
            label = "🔥 VERY HOT"

        elif deviation >= 3:
            label = "🟠 HOT"

        elif deviation <= -6:
            label = "❄️ VERY COLD"

        elif deviation <= -3:
            label = "🔵 COLD"

        else:
            label = "⚪ NEUTRAL"

        with cols[digit]:

            st.metric(
                str(digit),
                f"{pct:.1f}%"
            )

            st.caption(label)


    # ========================================================
    # OVER / UNDER
    # ========================================================

    st.markdown("## ↕️ Over / Under")

    ou1, ou2, ou3 = st.columns(3)

    with ou1:

        st.metric(
            "OVER 4",
            f"{analysis['over_pct']:.1f}%"
        )

    with ou2:

        st.metric(
            "UNDER 5",
            f"{analysis['under_pct']:.1f}%"
        )

    with ou3:

        difference = (
            analysis["over_pct"]
            -
            analysis["under_pct"]
        )

        if difference > 8:
            bias = "OVER"

        elif difference < -8:
            bias = "UNDER"

        else:
            bias = "NONE"

        st.metric(
            "Recent Bias",
            bias
        )


    # ========================================================
    # EVEN / ODD
    # ========================================================

    st.markdown("## ⚖️ Even / Odd")

    eo1, eo2, eo3 = st.columns(3)

    with eo1:
        st.metric(
            "EVEN",
            f"{analysis['even_pct']:.1f}%"
        )

    with eo2:
        st.metric(
            "ODD",
            f"{analysis['odd_pct']:.1f}%"
        )

    with eo3:

        difference = (
            analysis["even_pct"] - 50
        )

        if difference > 8:
            bias = "EVEN"

        elif difference < -8:
            bias = "ODD"

        else:
            bias = "NONE"

        st.metric(
            "Bias",
            bias
        )


    # ========================================================
    # RECENT DIGITS
    # ========================================================

    st.markdown("## 🧾 Last 30 Digits")

    recent_digits = [
        get_last_digit(x)
        for x in ticks[-30:]
    ]

    st.code(
        " ".join(
            str(x)
            for x in recent_digits
        )
    )


    # ========================================================
    # IMPORTANT DISCLAIMER
    # ========================================================

    st.warning(
        "⚠️ Educational analysis only. "
        "Recent frequency imbalance does not establish "
        "the outcome of the next tick. Test any strategy "
        "on a Deriv DEMO account before risking money."
    )


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_refresh:

    time.sleep(refresh)

    st.rerun()
