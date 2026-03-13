import streamlit as st
import random
import pandas as pd
import pydeck as pdk

# --- Simulation Constants ---
BASE_DEMAND = 80 
STARTING_INVENTORY = 160 
HOLDING_COST = 5 
STOCKOUT_PENALTY = 200 
SIMULATION_DAYS = 30

# --- The 4 Supply Chain Routes ---
ROUTES = {
    "Route A (Middle East via Hormuz)": {
        "lead_time": 3, "base_cost": 500, "risk_level": 0.30, 
        "color": [255, 50, 50] 
    },
    "Route B (USA via Cape of Good Hope)": {
        "lead_time": 15, "base_cost": 850, "risk_level": 0.05,
        "color": [50, 150, 255] 
    },
    "Route C (Emergency Overland / Spot Market)": {
        "lead_time": 1, "base_cost": 1200, "risk_level": 0.02,
        "color": [50, 255, 50] 
    },
    "Route D (Red Sea via Suez Canal)": {
        "lead_time": 8, "base_cost": 650, "risk_level": 0.45,
        "color": [255, 165, 0] 
    }
}

INDIA_PORT = [72.8777, 19.0760] 
ROUTE_COORDS = [
    {"route": "Route A", "start": [54.3773, 24.4539], "end": INDIA_PORT, "color": [255, 50, 50], "name": "Middle East"},
    {"route": "Route B", "start": [-95.0, 29.0], "end": INDIA_PORT, "color": [50, 150, 255], "name": "USA Gulf Coast"},
    {"route": "Route C", "start": [60.0, 40.0], "end": INDIA_PORT, "color": [50, 255, 50], "name": "Central Asia (Overland)"},
    {"route": "Route D", "start": [32.2846, 26.8206], "end": INDIA_PORT, "color": [255, 165, 0], "name": "Red Sea / Egypt"}
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
    
    # New Global Market Variables
    st.session_state.global_price_multiplier = 1.0
    st.session_state.shock_days_left = 0
    
    st.session_state.event_messages = ["Simulation started. Manage your supply."]
    st.session_state.bullwhip_active = False

if 'day' not in st.session_state:
    init_state()

# --- Game Logic ---
def advance_day(order_qty, selected_route):
    messages = []
    
    # 1. Manage Global Market Shocks
    if st.session_state.shock_days_left > 0:
        st.session_state.shock_days_left -= 1
        if st.session_state.shock_days_left == 0:
            st.session_state.global_price_multiplier = 1.0
            messages.append("✅ Global oil markets have stabilized. Prices returning to normal.")
    
    # 8% chance per day for a global panic to start
    elif random.random() < 0.08:
        st.session_state.shock_days_left = random.randint(3, 7)
        st.session_state.global_price_multiplier = 1.40 # 40% spike in route costs
        messages.append("🌍 GLOBAL SHOCK: Geopolitical panic! Worldwide hoarding is driving up oil prices and local demand!")

    # 2. Calculate Today's Demand
    base_variation = random.randint(-10, 15)
    today_demand = BASE_DEMAND + base_variation
    
    if st.session_state.shock_days_left > 0:
        today_demand += 25 # Local hoarding due to global shock
        if "🌍 GLOBAL SHOCK" not in messages[0] if messages else True:
            messages.append("📈 High Demand: Global hoarding panic is inflating daily requests.")
            
    if st.session_state.bullwhip_active:
        today_demand = int(today_demand * 1.6) 
        messages.append("⚠️ BULLWHIP EFFECT: Public panic buying due to recent shortages!")
        st.session_state.bullwhip_active = False 

    # 3. Process Arrivals from Pipeline
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

    # 4. Fulfill Demand & Calculate Shortages
    stockout_today = 0
    if st.session_state.inventory >= today_demand:
        st.session_state.inventory -= today_demand
    else:
        stockout_today = today_demand - st.session_state.inventory
        st.session_state.inventory = 0
        st.session_state.total_stockout += stockout_today
        st.session_state.bullwhip_active = True 

    # 5. Calculate Costs
    holding_cost_today = st.session_state.inventory * HOLDING_COST
    penalty_cost_today = stockout_today * STOCKOUT_PENALTY
    st.session_state.total_cost += holding_cost_today + penalty_cost_today

    # 6. Process New Order
    if order_qty > 0:
        route_info = ROUTES[selected_route]
        current_cost = int(route_info["base_cost"] * st.session_state.global_price_multiplier)
        
        if random.random() < route_info["risk_level"]:
            delay = random.randint(7, 14) if "Red Sea" in selected_route else random.randint(2, 6)
            arrival = st.session_state.day + route_info["lead_time"] + delay
            messages.append(f"🚨 DISRUPTION: {selected_route} blocked! Delayed by {delay} days.")
        else:
            arrival = st.session_state.day + route_info["lead_time"]
            
        st.session_state.pipeline.append({
            'arrival_day': arrival,
            'qty': order_qty,
            'cost': current_cost, # Lock in the price at the time of order
            'route': selected_route
        })

    if not messages:
        messages.append("Standard market conditions.")
    st.session_state.event_messages = messages

    # 7. Record History and Advance Time
    st.session_state.history.append({
        "Day": st.session_state.day,
        "Inventory": st.session_state.inventory,
        "Demand": today_demand,
        "Stockout": stockout_today,
        "Price_Multiplier": st.session_state.global_price_multiplier
    })

    st.session_state.day += 1
    if st.session_state.day > SIMULATION_DAYS:
        st.session_state.game_over = True

# --- UI Layout ---
st.set_page_config(page_title="India LPG Simulator", layout="wide")
st.title("🛢️ India LPG Supply Chain Simulator")

if not st.session_state.game_over:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Day", f"{st.session_state.day} / {SIMULATION_DAYS}")
    col2.metric("Current Inventory", f"{st.session_state.inventory} TMT")
    col3.metric("Total Cost", f"${st.session_state.total_cost:,}")
    
    market_state = "🚨 High Volatility" if st.session_state.shock_days_left > 0 else "🟢 Stable"
    col4.metric("Global Oil Market", market_state, f"{int(st.session_state.global_price_multiplier * 100)}% Price Level", delta_color="inverse")

    # Display dynamic alerts
    for msg in st.session_state.event_messages:
        if "🚨" in msg or "⚠️" in msg or "🌍" in msg:
            st.error(msg)
        elif "✅" in msg:
            st.success(msg)
        elif "📈" in msg:
            st.warning(msg)
        else:
            st.info(msg)

    # --- Render PyDeck Map ---
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
            
            # Formatter function to show full route names and DYNAMIC costs
            def format_route(r):
                current_price = int(ROUTES[r]['base_cost'] * st.session_state.global_price_multiplier)
                lead = ROUTES[r]['lead_time']
                risk = int(ROUTES[r]['risk_level'] * 100)
                return f"{r} | Lead: {lead}d | Cost: ${current_price} | Risk: {risk}%"

            selected_route = st.radio(
                "Routes", 
                list(ROUTES.keys()), 
                format_func=format_route,
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
            st.dataframe(pipeline_df.rename(columns={'arrival_day': 'Arrival', 'qty': 'Qty', 'cost': 'Locked Cost ($)', 'route': 'Route'}), use_container_width=True)
        else:
            st.write("*No incoming shipments.*")

else:
    st.success("Simulation Complete!")
    base_budget = (BASE_DEMAND * SIMULATION_DAYS) * ROUTES["Route A (Middle East via Hormuz)"]["base_cost"]
    final_score = base_budget - st.session_state.total_cost
    
    st.subheader("Performance Review")
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("Total Cost", f"${st.session_state.total_cost:,}")
    col_s2.metric("Total Unmet Demand", st.session_state.total_stockout)
    col_s3.metric("Final Score", f"{final_score:,}")
    
    st.markdown("### 30-Day Operational History")
    df_history = pd.DataFrame(st.session_state.history).set_index("Day")
    st.line_chart(df_history[["Inventory", "Demand", "Stockout"]])

    # ... (existing performance review code) ...

    st.markdown("---")
    st.subheader("📥 Export Data for Researcher")
    st.write("Please download your results and email the file to the researcher.")
    
    # 1. Convert the session history list into a Pandas DataFrame
    df_history = pd.DataFrame(st.session_state.history)
    
    # Add final score and total costs as columns so they are saved in the data
    df_history['Final_Score'] = final_score
    df_history['Total_Cost'] = st.session_state.total_cost
    df_history['Total_Stockout'] = st.session_state.total_stockout
    
    # 2. Convert DataFrame to CSV format natively
    csv_data = df_history.to_csv(index=False).encode('utf-8')
    
    # 3. Create the Download Button
    st.download_button(
        label="Download Simulation Results (CSV)",
        data=csv_data,
        file_name="lpg_simulation_results.csv",
        mime="text/csv"
    )
    
    if st.button("Restart Simulation"):
        init_state()
        st.rerun()
    
    if st.button("Restart Simulation"):
        init_state()
        st.rerun()
