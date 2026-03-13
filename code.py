import streamlit as st
import random
import pandas as pd
import pydeck as pdk

# --- Simulation Constants ---
BASE_DEMAND = 80 # TMT per day
STARTING_INVENTORY = 160 
HOLDING_COST = 5 
STOCKOUT_PENALTY = 200 
SIMULATION_DAYS = 30

# --- The 3 Supply Chain Routes ---
ROUTES = {
    "Route A (Middle East via Hormuz)": {
        "lead_time": 3, "cost": 500, "risk_level": 0.30, 
        "desc": "Cheap & Fast. High geopolitical risk.",
        "color": [255, 50, 50] # Red
    },
    "Route B (USA via Cape of Good Hope)": {
        "lead_time": 15, "cost": 850, "risk_level": 0.05,
        "desc": "Expensive & Slow. Very safe.",
        "color": [50, 150, 255] # Blue
    },
    "Route C (Emergency Overland / Spot Market)": {
        "lead_time": 1, "cost": 1200, "risk_level": 0.02,
        "desc": "Immediate delivery. Exorbitant cost.",
        "color": [50, 255, 50] # Green
    }
}

# Geocoordinates for PyDeck Map: [Longitude, Latitude]
INDIA_PORT = [72.8777, 19.0760] # Mumbai
ROUTE_COORDS = [
    {"route": "Route A", "start": [54.3773, 24.4539], "end": INDIA_PORT, "color": [255, 50, 50], "name": "Middle East"},
    {"route": "Route B", "start": [-95.0, 29.0], "end": INDIA_PORT, "color": [50, 150, 255], "name": "USA Gulf Coast"},
    {"route": "Route C", "start": [60.0, 40.0], "end": INDIA_PORT, "color": [50, 255, 50], "name": "Central Asia (Overland)"}
]

# --- Initialize State ---
def init_state():
    st.session_state.day = 1
    st.session_state.inventory = STARTING_INVENTORY
    st.session_state.pipeline = [] 
    st.session_state.history = []
    st.session_state.total_cost = 0
    st.session_state.total_stockout = 0
    st.session_state.game_over = False
    st.session_state.event_message = "Simulation started. Manage your supply."
    st.session_state.bullwhip_active = False

if 'day' not in st.session_state:
    init_state()

# --- Game Logic ---
def advance_day(order_qty, selected_route):
    base_variation = random.randint(-10, 15)
    today_demand = BASE_DEMAND + base_variation
    
    if random.random() < 0.10:
        today_demand -= 25
        st.session_state.event_message = "Economic slowdown: Demand dropped today."
    
    if st.session_state.bullwhip_active:
        today_demand = int(today_demand * 1.6) 
        st.session_state.event_message = "⚠️ BULLWHIP EFFECT: Public panic buying due to recent shortages!"
        st.session_state.bullwhip_active = False 
    else:
        st.session_state.event_message = "Standard demand conditions."

    arrived_today = 0
    remaining_pipeline = []
    for order in st.session_state.pipeline:
        if order['arrival_day'] == st.session_state.day:
            arrived_today += order['qty']
            st.session_state.total_cost += order['cost'] * order['qty']
        else:
            remaining_pipeline.append(order)
    st.session_state.pipeline = remaining_pipeline
    st.session_state.inventory += arrived_today

    stockout_today = 0
    if st.session_state.inventory >= today_demand:
        st.session_state.inventory -= today_demand
    else:
        stockout_today = today_demand - st.session_state.inventory
        st.session_state.inventory = 0
        st.session_state.total_stockout += stockout_today
        st.session_state.bullwhip_active = True 

    holding_cost_today = st.session_state.inventory * HOLDING_COST
    penalty_cost_today = stockout_today * STOCKOUT_PENALTY
    st.session_state.total_cost += holding_cost_today + penalty_cost_today

    if order_qty > 0:
        route_info = ROUTES[selected_route]
        if random.random() < route_info["risk_level"]:
            delay = random.randint(2, 6)
            arrival = st.session_state.day + route_info["lead_time"] + delay
            st.session_state.event_message += f" | 🚨 DISRUPTION: {selected_route[:7]} delayed by {delay} days!"
        else:
            arrival = st.session_state.day + route_info["lead_time"]
            
        st.session_state.pipeline.append({
            'arrival_day': arrival,
            'qty': order_qty,
            'cost': route_info["cost"],
            'route': selected_route
        })

    st.session_state.history.append({
        "Day": st.session_state.day,
        "Inventory": st.session_state.inventory,
        "Demand": today_demand,
        "Stockout": stockout_today
    })

    st.session_state.day += 1
    if st.session_state.day > SIMULATION_DAYS:
        st.session_state.game_over = True

# --- UI Layout ---
st.set_page_config(page_title="India LPG Simulator", layout="wide")
st.title("🛢️ India LPG Supply Chain Simulator")

if not st.session_state.game_over:
    col1, col2, col3 = st.columns(3)
    col1.metric("Day", f"{st.session_state.day} / {SIMULATION_DAYS}")
    col2.metric("Current Inventory", f"{st.session_state.inventory} TMT")
    col3.metric("Total Cost", f"${st.session_state.total_cost:,}")

    if "🚨" in st.session_state.event_message or "⚠️" in st.session_state.event_message:
        st.error(st.session_state.event_message)
    else:
        st.info(st.session_state.event_message)

    # --- Render PyDeck Map ---
    st.markdown("### Global Supply Routes")
    arc_layer = pdk.Layer(
        "ArcLayer",
        data=ROUTE_COORDS,
        get_source_position="start",
        get_target_position="end",
        get_source_color="color",
        get_target_color="color",
        get_width=5,
        pickable=True,
        auto_highlight=True,
    )
    
    view_state = pdk.ViewState(latitude=20.0, longitude=35.0, zoom=1.5, pitch=45)
    st.pydeck_chart(pdk.Deck(layers=[arc_layer], initial_view_state=view_state, tooltip={"text": "{name} to India"}))

    col_form, col_pipeline = st.columns([1, 1])
    
    with col_form:
        st.subheader("Daily Supply Decision")
        with st.form("order_form"):
            order_qty = st.number_input("Order Quantity (TMT)", min_value=0, max_value=500, value=80, step=10)
            st.write("**Select Shipping Route:**")
            selected_route = st.radio(
                "Routes", 
                list(ROUTES.keys()), 
                format_func=lambda x: f"{x[:7]} - Lead: {ROUTES[x]['lead_time']}d | Cost: ${ROUTES[x]['cost']} | Risk: {int(ROUTES[x]['risk_level']*100)}%",
                label_visibility="collapsed"
            )
            submit = st.form_submit_button("Submit Order & Advance Day")
            if submit:
                advance_day(order_qty, selected_route)
                st.rerun()

    with col_pipeline:
        st.subheader("Incoming Shipments")
        if st.session_state.pipeline:
            pipeline_df = pd.DataFrame(st.session_state.pipeline)
            st.dataframe(pipeline_df.rename(columns={'arrival_day': 'Arrival', 'qty': 'Qty', 'cost': 'Cost', 'route': 'Route'}), use_container_width=True)
        else:
            st.write("*No incoming shipments.*")

else:
    st.success("Simulation Complete!")
    base_budget = (BASE_DEMAND * SIMULATION_DAYS) * ROUTES["Route A (Middle East via Hormuz)"]["cost"]
    final_score = base_budget - st.session_state.total_cost
    
    st.subheader("Performance Review")
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("Total Cost", f"${st.session_state.total_cost:,}")
    col_s2.metric("Total Unmet Demand", st.session_state.total_stockout)
    col_s3.metric("Final Score", f"{final_score:,}")
    
    st.markdown("### 30-Day Operational History")
    df_history = pd.DataFrame(st.session_state.history).set_index("Day")
    st.line_chart(df_history[["Inventory", "Demand", "Stockout"]])
    
    if st.button("Restart Simulation"):
        init_state()
        st.rerun()
