"""
🛢️  INDIA LPG SUPPLY CHAIN SIMULATOR  —  "The Hormuz Crisis"
==============================================================
A teaching / research simulation grounded in the real 2026 India LPG crunch.

REAL-WORLD FACTS THIS MODEL IS BUILT ON
---------------------------------------
• India imports ~60% of its LPG and consumes ~90,000 tonnes/day (~90 TMT).
• ~90% of those imports normally transit the Strait of Hormuz.
• Middle-East LPG is butane-heavy = India's correct household blend (60% butane / 40% propane).
  US / Atlantic LPG is propane-heavy and needs extra blending -> lower usable yield.
• US cargoes take ~40 days vs <10 days from the Gulf.
• Storage is thin: national LPG storage ~1.34 MMT (~2 weeks); strategic reserves < 2 days.
• Price driver = Saudi Aramco Contract Price (CP). Propane went $525/mt (Jan'26) -> $750/mt (Apr'26).
• Trigger event: US/Israeli strikes on Iran, 28 Feb 2026, effectively closing Hormuz.
• Real govt responses (modelled here as levers): +25% domestic output; demand rationing
  (LPG booking gap raised 21 -> 25 days); household-first allocation.

Run with:  streamlit run lpg_simulator.py
"""

import streamlit as st
import random
import pandas as pd
import pydeck as pdk

# =====================================================================
# SIMULATION CONSTANTS  (grounded in real figures, scaled to TMT/day)
# =====================================================================
SIMULATION_DAYS       = 30
BASE_NATIONAL_DEMAND  = 90    # TMT/day  -> real ~90 kt/day national consumption
BASE_DOMESTIC_OUTPUT  = 36    # TMT/day  -> ~40% met domestically; rest is imports
STARTING_INVENTORY    = 280   # TMT      -> a few days of the import gap (tight, like reality)
STORAGE_CAPACITY      = 650   # TMT      -> hard cap; you physically cannot hoard forever
HOLDING_COST          = 18    # cost index per TMT per day sitting in tanks
STOCKOUT_PENALTY      = 900   # cost index per TMT of unmet household demand (welfare-critical)

# Saudi Aramco CP band (USD/tonne) — used as the live market signal & cost driver
CP_NORMAL             = 525   # ~ Jan 2026 real level
CP_CRISIS             = 750   # ~ Apr 2026 real crisis level

# =====================================================================
# THE 4 SUPPLY ROUTES  (realistic trade-offs)
# =====================================================================
# blend  = usable fraction of the cargo for household demand (propane-heavy => <1.0)
# risk   = base chance of disruption/delay on departure
ROUTES = {
    "A · Middle East (Strait of Hormuz)": {
        "lead_time": 4,  "base_cost": 520,  "base_risk": 0.12, "blend": 1.00,
        "color": [239, 68, 68],
        "note": "Cheapest, fastest, correct butane blend — but 90% of imports rely on it. Hormuz risk spikes in a crisis.",
    },
    "B · US Gulf Coast (long-haul, Cape route)": {
        "lead_time": 20, "base_cost": 880,  "base_risk": 0.05, "blend": 0.88,
        "color": [59, 130, 246],
        "note": "Very safe & reliable, but ~40-day real transit and propane-heavy (needs blending -> ~88% usable).",
    },
    "C · West Africa / Atlantic (Algeria, Nigeria, Argentina)": {
        "lead_time": 12, "base_cost": 700,  "base_risk": 0.15, "blend": 0.95,
        "color": [234, 179, 8],
        "note": "Diversification play. Medium cost & speed, decent blend, moderate route risk.",
    },
    "D · Emergency Spot Charter (VLGC)": {
        "lead_time": 2,  "base_cost": 1550, "base_risk": 0.03, "blend": 1.00,
        "color": [34, 197, 94],
        "note": "Bails you out in ~2 days at an eye-watering price. Use only to prevent a stockout.",
    },
}

# =====================================================================
# MAP GEOGRAPHY (approx real coordinates: origin ports -> India)
# =====================================================================
INDIA_PORT = [72.95, 18.95]  # JNPT / Mumbai region
HORMUZ     = [56.45, 26.57]  # Strait of Hormuz chokepoint

ROUTE_COORDS = [
    {"route": "A", "start": [50.16, 26.64], "end": INDIA_PORT, "color": [239, 68, 68],  "name": "Ras Tanura → India (via Hormuz)"},
    {"route": "B", "start": [-95.0, 29.0],  "end": INDIA_PORT, "color": [59, 130, 246], "name": "US Gulf Coast → India (via Cape)"},
    {"route": "C", "start": [-0.30, 35.80],  "end": INDIA_PORT, "color": [234, 179, 8],  "name": "Arzew (Algeria) → India"},
    {"route": "D", "start": [56.33, 25.12], "end": INDIA_PORT, "color": [34, 197, 94],  "name": "Fujairah spot charter → India"},
]

PORTS = [
    {"name": "Mumbai / JNPT (India)", "coord": INDIA_PORT, "color": [255, 255, 255]},
    {"name": "Strait of Hormuz",      "coord": HORMUZ,     "color": [239, 68, 68]},
]

SCENARIOS = {
    "🔴 Hormuz Crisis (Feb 2026)": {"hormuz_tension": 1.0, "start_cp": CP_CRISIS, "desc": "Hard mode. Hormuz is inflamed from day one — high risk, high prices."},
    "🟡 Rising Tension":           {"hormuz_tension": 0.5, "start_cp": 620,        "desc": "Medium mode. Markets are jittery; shocks are more frequent."},
    "🟢 Normal Operations":        {"hormuz_tension": 0.0, "start_cp": CP_NORMAL,  "desc": "Easy mode. Calm seas — learn the mechanics before the storm."},
}


# =====================================================================
# STATE
# =====================================================================
def init_state():
    st.session_state.game_started   = False
    st.session_state.participant_id = ""
    st.session_state.scenario       = "🔴 Hormuz Crisis (Feb 2026)"
    st.session_state.day            = 1
    st.session_state.inventory      = STARTING_INVENTORY
    st.session_state.pipeline       = []
    st.session_state.history        = []
    st.session_state.total_cost     = 0
    st.session_state.purchase_cost  = 0
    st.session_state.holding_total  = 0
    st.session_state.penalty_total  = 0
    st.session_state.total_stockout = 0
    st.session_state.game_over      = False
    st.session_state.public_confidence = 100
    # market
    st.session_state.saudi_cp       = CP_NORMAL
    st.session_state.hormuz_tension = 0.0   # 0..1, scales Route A risk & prices
    st.session_state.shock_days_left = 0
    st.session_state.bullwhip_active = False
    # government levers
    st.session_state.domestic_output = BASE_DOMESTIC_OUTPUT
    st.session_state.boost_days_left = 0
    st.session_state.boost_used      = False
    st.session_state.ration_days_left = 0
    st.session_state.ration_charges  = 2
    st.session_state.event_messages  = ["Simulation initialised. Manage the national LPG balance."]


if "day" not in st.session_state:
    init_state()

st.set_page_config(page_title="India LPG Crisis Simulator", page_icon="🛢️", layout="wide")


# =====================================================================
# 1) WELCOME / BRIEFING SCREEN
# =====================================================================
if not st.session_state.game_started:
    st.title("🛢️ India LPG Supply Chain Simulator")
    st.subheader("Mission Briefing — *The Hormuz Crisis*")

    with st.container(border=True):
        st.markdown(
            """
            You are the **Chief Logistics Officer** for India's national cooking-gas (LPG) supply.
            For **30 days** you must keep **~90 TMT/day** of demand met while global markets and a
            maritime crisis work against you.

            **Why this is hard (and real):** India imports **~60%** of its LPG, and **~90%** of those
            imports pass through the **Strait of Hormuz**. In this scenario that chokepoint is inflamed
            following the Feb 2026 strikes on Iran. Storage is thin (national capacity ≈ 2 weeks of use),
            so a single missed shipment cascades into a household shortage fast.
            """
        )

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### 🚢 Your four supply routes")
            st.markdown(
                """
                - **A · Middle East (Hormuz)** — cheap, fast, correct butane blend. **But** Hormuz risk spikes in crisis.
                - **B · US Gulf Coast** — very safe, but ~20-day transit and propane-heavy (**~88% usable**).
                - **C · West Africa / Atlantic** — diversification: medium cost/speed, decent blend.
                - **D · Emergency Spot Charter** — arrives in ~2 days to save you, at a brutal price.
                """
            )
    with c2:
        with st.container(border=True):
            st.markdown("#### ⚠️ Hidden dangers")
            st.markdown(
                f"""
                - **Holding cost** — every idle TMT costs **{HOLDING_COST}/day**. Storage caps at **{STORAGE_CAPACITY} TMT**.
                - **Stockout penalty** — hitting 0 costs **{STOCKOUT_PENALTY}/TMT** of unmet demand.
                - **Bullwhip effect** — a stockout triggers panic hoarding: demand spikes next day.
                - **Global shocks** — Hormuz flare-ups raise the **Saudi CP** and freight. Orders locked *before* a shock keep their price.
                """
            )

    with st.container(border=True):
        st.markdown("#### 🏛️ Government levers you control")
        st.markdown(
            """
            - **Boost Domestic Output (+25%)** — divert refinery streams to LPG for a few days *(one-time)*.
            - **Demand Rationing** — raise the booking gap (21→25 days) to cut demand briefly, at a small hit to **Public Confidence** *(limited use)*.
            """
        )

    st.warning("⚠️ At the end of Day 30, **download your CSV report** before restarting.")
    st.markdown("---")

    st.subheader("Participant Registration")
    with st.form("login_form"):
        p_id = st.text_input("Participant ID or Name (required)")
        scen = st.radio(
            "Choose scenario difficulty",
            list(SCENARIOS.keys()),
            format_func=lambda s: f"{s} — {SCENARIOS[s]['desc']}",
        )
        start_btn = st.form_submit_button("▶ Start Simulation", use_container_width=True)
        if start_btn:
            if p_id.strip() == "":
                st.error("You must enter a Participant ID to continue.")
            else:
                st.session_state.participant_id = p_id.strip()
                st.session_state.scenario       = scen
                st.session_state.hormuz_tension = SCENARIOS[scen]["hormuz_tension"]
                st.session_state.saudi_cp       = SCENARIOS[scen]["start_cp"]
                st.session_state.game_started   = True
                st.rerun()


# =====================================================================
# 2) MAIN GAME BOARD
# =====================================================================
elif not st.session_state.game_over:

    # ---------------- core turn logic ----------------
    def route_current_cost(route_name):
        r = ROUTES[route_name]
        # cost scales with the live Saudi CP vs the normal baseline
        cp_factor = st.session_state.saudi_cp / CP_NORMAL
        extra = 0.0
        if route_name.startswith("A"):
            extra = 0.35 * st.session_state.hormuz_tension  # war-risk premium on the Gulf route
        return int(r["base_cost"] * cp_factor * (1 + extra))

    def route_current_risk(route_name):
        r = ROUTES[route_name]
        risk = r["base_risk"]
        if route_name.startswith("A"):
            risk += 0.45 * st.session_state.hormuz_tension  # Hormuz danger loads onto Route A
        return min(risk, 0.9)

    def advance_day(order_qty, selected_route):
        messages = []
        s = st.session_state

        # -- 1. market / Hormuz drift --
        if s.shock_days_left > 0:
            s.shock_days_left -= 1
            if s.shock_days_left == 0:
                s.saudi_cp = max(CP_NORMAL, s.saudi_cp - 120)
                s.hormuz_tension = max(0.0, s.hormuz_tension - 0.3)
                messages.append("✅ Markets cooling: Saudi CP easing and Hormuz tension down.")
        else:
            # chance of a fresh shock rises with baseline tension
            if random.random() < 0.08 + 0.12 * s.hormuz_tension:
                s.shock_days_left = random.randint(3, 7)
                s.saudi_cp = min(CP_CRISIS + 40, s.saudi_cp + random.randint(80, 160))
                s.hormuz_tension = min(1.0, s.hormuz_tension + 0.3)
                messages.append("🌍 GLOBAL SHOCK: Hormuz flare-up — Saudi CP and freight are spiking!")

        # gentle CP mean-reversion when calm
        if s.shock_days_left == 0:
            drift = random.randint(-15, 15)
            target = CP_NORMAL + (CP_CRISIS - CP_NORMAL) * s.hormuz_tension
            s.saudi_cp = int(0.85 * s.saudi_cp + 0.15 * target + drift)

        # -- 2. government levers timers --
        if s.boost_days_left > 0:
            s.boost_days_left -= 1
            s.domestic_output = int(BASE_DOMESTIC_OUTPUT * 1.25)
            if s.boost_days_left == 0:
                s.domestic_output = BASE_DOMESTIC_OUTPUT
                messages.append("ℹ️ Emergency domestic production boost has ended.")
        else:
            s.domestic_output = BASE_DOMESTIC_OUTPUT

        rationing = s.ration_days_left > 0
        if rationing:
            s.ration_days_left -= 1

        # -- 3. demand --
        demand = BASE_NATIONAL_DEMAND + random.randint(-8, 12)
        if s.shock_days_left > 0:
            demand += 18
            messages.append("📈 Panic demand: households and induction-stove buyers are stockpiling.")
        if s.bullwhip_active:
            demand = int(demand * 1.55)
            messages.append("⚠️ BULLWHIP: public panic buying after the recent shortage!")
            s.bullwhip_active = False
        if rationing:
            demand = int(demand * 0.88)
            messages.append("🏛️ Rationing in effect: booking gap widened, demand temporarily eased.")

        # domestic output covers part of demand; the rest is the IMPORT gap you must fill
        import_gap = max(0, demand - s.domestic_output)

        # -- 4. arrivals from pipeline (usable qty already blend-adjusted) --
        arrived, remaining = 0, []
        for o in s.pipeline:
            if o["arrival_day"] == s.day:
                arrived += o["usable_qty"]
                s.purchase_cost += o["cost"] * o["order_qty"]
                s.total_cost    += o["cost"] * o["order_qty"]
            else:
                remaining.append(o)
        s.pipeline = remaining
        s.inventory += arrived

        # storage cap — cannot physically hold more than capacity
        if s.inventory > STORAGE_CAPACITY:
            wasted = s.inventory - STORAGE_CAPACITY
            s.inventory = STORAGE_CAPACITY
            messages.append(f"🛢️ Storage full: {wasted} TMT could not be received (capacity {STORAGE_CAPACITY}).")

        # -- 5. serve demand --
        stockout = 0
        if s.inventory >= import_gap:
            s.inventory -= import_gap
        else:
            stockout = import_gap - s.inventory
            s.inventory = 0
            s.total_stockout += stockout
            s.bullwhip_active = True
            s.public_confidence = max(0, s.public_confidence - min(25, stockout // 2 + 5))

        # -- 6. daily costs --
        holding = s.inventory * HOLDING_COST
        penalty = stockout * STOCKOUT_PENALTY
        s.holding_total += holding
        s.penalty_total += penalty
        s.total_cost    += holding + penalty

        # slow confidence recovery when supplied
        if stockout == 0:
            s.public_confidence = min(100, s.public_confidence + 2)

        # -- 7. place new order --
        if order_qty > 0:
            r = ROUTES[selected_route]
            cost = route_current_cost(selected_route)
            if random.random() < route_current_risk(selected_route):
                delay = random.randint(5, 12) if selected_route.startswith("A") else random.randint(2, 6)
                arrival = s.day + r["lead_time"] + delay
                messages.append(f"🚨 DISRUPTION: {selected_route[:1]}-route order delayed +{delay} days!")
            else:
                arrival = s.day + r["lead_time"]
            usable = int(order_qty * r["blend"])
            s.pipeline.append({
                "arrival_day": arrival,
                "order_qty": order_qty,
                "usable_qty": usable,
                "cost": cost,
                "route": selected_route.split(" ")[0] + selected_route.split("·")[0],
            })
            if r["blend"] < 1.0:
                messages.append(f"🧪 Blend note: propane-heavy cargo → only {usable}/{order_qty} TMT usable for households.")

        if not messages:
            messages.append("🟢 Standard market conditions.")
        s.event_messages = messages

        # -- 8. record + advance --
        s.history.append({
            "Participant_ID": s.participant_id,
            "Scenario": s.scenario,
            "Day": s.day,
            "Inventory": s.inventory,
            "National_Demand": demand,
            "Domestic_Output": s.domestic_output,
            "Import_Gap": import_gap,
            "Stockout": stockout,
            "Saudi_CP_USD": s.saudi_cp,
            "Hormuz_Tension": round(s.hormuz_tension, 2),
            "Public_Confidence": s.public_confidence,
            "Daily_Cost": holding + penalty,
        })
        s.day += 1
        if s.day > SIMULATION_DAYS:
            s.game_over = True

    # ---------------- SIDEBAR: reference + levers ----------------
    with st.sidebar:
        st.header("📋 Reference")
        st.caption(f"Officer: **{st.session_state.participant_id}**  \nScenario: {st.session_state.scenario}")
        st.markdown(
            f"""
            **Targets**
            - Nat. demand ≈ {BASE_NATIONAL_DEMAND} TMT/day
            - Domestic output ≈ {st.session_state.domestic_output} TMT/day
            - Storage cap = {STORAGE_CAPACITY} TMT

            **Costs**
            - Holding: {HOLDING_COST}/TMT/day
            - Stockout: {STOCKOUT_PENALTY}/TMT
            """
        )
        st.divider()
        st.subheader("🏛️ Government levers")

        if st.session_state.boost_used:
            st.button("Boost Domestic Output", disabled=True, help="Already used this game.", use_container_width=True)
        else:
            if st.button("⚡ Boost Domestic Output (+25%, 5d)", use_container_width=True):
                st.session_state.boost_days_left = 5
                st.session_state.boost_used = True
                st.session_state.event_messages = ["⚡ Refineries diverting streams: domestic LPG output +25% for 5 days."]
                st.rerun()

        if st.session_state.ration_charges > 0:
            if st.button(f"📉 Demand Rationing (−12%, 3d) · {st.session_state.ration_charges} left", use_container_width=True):
                st.session_state.ration_days_left = 3
                st.session_state.ration_charges -= 1
                st.session_state.public_confidence = max(0, st.session_state.public_confidence - 6)
                st.session_state.event_messages = ["📉 Rationing announced: booking gap 21→25 days. Confidence dips slightly."]
                st.rerun()
        else:
            st.button("Demand Rationing", disabled=True, help="No charges left.", use_container_width=True)

        st.divider()
        if st.button("🔄 Restart", use_container_width=True):
            init_state()
            st.rerun()

    # ---------------- HEADER + METRICS ----------------
    st.title("🛢️ India LPG Crisis — Command Center")
    st.progress((st.session_state.day - 1) / SIMULATION_DAYS, text=f"Day {st.session_state.day} of {SIMULATION_DAYS}")

    m1, m2, m3, m4, m5 = st.columns(5)
    inv = st.session_state.inventory
    m1.metric("Inventory", f"{inv} TMT", f"cap {STORAGE_CAPACITY}")
    m2.metric("Total Cost", f"{st.session_state.total_cost:,}")
    m3.metric("Unmet Demand", f"{st.session_state.total_stockout} TMT")
    m4.metric("Public Confidence", f"{st.session_state.public_confidence}%")

    if st.session_state.hormuz_tension >= 0.66:
        hz = "🔴 Inflamed"
    elif st.session_state.hormuz_tension >= 0.33:
        hz = "🟡 Tense"
    else:
        hz = "🟢 Open"
    m5.metric("Saudi CP", f"${st.session_state.saudi_cp}/mt", hz, delta_color="off")

    # ---------------- EVENT FEED ----------------
    for msg in st.session_state.event_messages:
        if any(t in msg for t in ("🚨", "⚠️", "🌍")):
            st.error(msg)
        elif "✅" in msg:
            st.success(msg)
        elif any(t in msg for t in ("📈", "🛢️", "📉")):
            st.warning(msg)
        else:
            st.info(msg)

    # ---------------- MAP ----------------
    arc_layer = pdk.Layer(
        "ArcLayer", data=ROUTE_COORDS,
        get_source_position="start", get_target_position="end",
        get_source_color="color", get_target_color="color",
        get_width=4, pickable=True, auto_highlight=True,
    )
    port_layer = pdk.Layer(
        "ScatterplotLayer", data=[{"coord": p["coord"], "name": p["name"], "color": p["color"]} for p in PORTS],
        get_position="coord", get_fill_color="color", get_radius=140000, pickable=True,
    )
    view = pdk.ViewState(latitude=22.0, longitude=42.0, zoom=2.6, pitch=40)
    st.pydeck_chart(pdk.Deck(
        layers=[arc_layer, port_layer], initial_view_state=view,
        map_style=None, tooltip={"text": "{name}"},
    ))

    # ---------------- ORDER FORM + PIPELINE ----------------
    left, right = st.columns([1, 1])

    with left:
        st.subheader("📦 Daily Supply Decision")
        with st.form("order_form"):
            qty = st.number_input("Order Quantity (TMT)", min_value=0, max_value=500, value=80, step=10)

            def fmt(r):
                return (f"{r} · Lead {ROUTES[r]['lead_time']}d · Cost {route_current_cost(r)} · "
                        f"Risk {int(route_current_risk(r)*100)}% · Usable {int(ROUTES[r]['blend']*100)}%")

            route = st.radio("Route", list(ROUTES.keys()), format_func=fmt, label_visibility="collapsed")
            st.caption(ROUTES[route]["note"])
            submit = st.form_submit_button("✅ Submit Order & Advance Day", use_container_width=True)
            if submit:
                advance_day(qty, route)
                st.rerun()

    with right:
        st.subheader("🚢 Incoming Shipments")
        if st.session_state.pipeline:
            df = pd.DataFrame(st.session_state.pipeline)
            df["ETA (days)"] = df["arrival_day"] - st.session_state.day
            show = df[["route", "order_qty", "usable_qty", "cost", "arrival_day", "ETA (days)"]].rename(
                columns={"route": "Route", "order_qty": "Ordered", "usable_qty": "Usable",
                         "cost": "Locked Cost", "arrival_day": "Arr. Day"})
            st.dataframe(show, use_container_width=True, hide_index=True)
        else:
            st.info("No shipments currently in transit.")

        # quick days-of-cover gauge
        cover = st.session_state.inventory / max(1, BASE_NATIONAL_DEMAND - st.session_state.domestic_output)
        st.metric("Days of cover (at current gap)", f"{cover:.1f} days")


# =====================================================================
# 3) GAME OVER + DATA EXPORT
# =====================================================================
else:
    st.balloons()
    st.success("✅ Simulation Complete — 30 days survived.")

    # score: benchmark budget (all-Route-A at normal price) minus what you actually spent,
    # with a confidence bonus/penalty.
    benchmark = (BASE_NATIONAL_DEMAND - BASE_DOMESTIC_OUTPUT) * SIMULATION_DAYS * ROUTES["A · Middle East (Strait of Hormuz)"]["base_cost"]
    confidence_adj = (st.session_state.public_confidence - 100) * 200
    final_score = benchmark - st.session_state.total_cost + confidence_adj

    st.subheader(f"Performance Review — {st.session_state.participant_id}")

    a, b, c, d = st.columns(4)
    a.metric("Total Cost", f"{st.session_state.total_cost:,}")
    b.metric("Unmet Demand", f"{st.session_state.total_stockout} TMT")
    c.metric("Public Confidence", f"{st.session_state.public_confidence}%")
    d.metric("Final Score", f"{final_score:,}")

    with st.expander("💰 Cost breakdown"):
        st.write(f"- Purchase (freight + product): **{st.session_state.purchase_cost:,}**")
        st.write(f"- Holding costs: **{st.session_state.holding_total:,}**")
        st.write(f"- Stockout penalties: **{st.session_state.penalty_total:,}**")
        st.write(f"- Confidence adjustment: **{confidence_adj:,}**")

    df_hist = pd.DataFrame(st.session_state.history).set_index("Day")
    st.markdown("##### Inventory vs demand over time")
    st.line_chart(df_hist[["Inventory", "National_Demand", "Import_Gap", "Stockout"]])
    st.markdown("##### Market pressure (Saudi CP)")
    st.line_chart(df_hist[["Saudi_CP_USD"]])

    st.markdown("---")
    st.subheader("📥 Export Data for Researcher")
    st.write("Download your results and send the file to your instructor **before restarting**.")

    export = pd.DataFrame(st.session_state.history)
    export["Final_Score"]    = final_score
    export["Total_Cost"]     = st.session_state.total_cost
    export["Total_Stockout"] = st.session_state.total_stockout
    export["Final_Confidence"] = st.session_state.public_confidence

    fname = f"lpg_sim_{st.session_state.participant_id}.csv"
    st.download_button(
        "⬇️ Download Simulation Results (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=fname, mime="text/csv", use_container_width=True,
    )

    if st.button("🔄 Restart Simulation", key="final_restart"):
        init_state()
        st.rerun()
