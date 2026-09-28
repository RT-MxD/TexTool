import streamlit as st
import requests
import pandas as pd

# --- Configuration ---
API_BASE_URL = "https://textool.onrender.com"  # Update this if your API runs elsewhere
st.set_page_config(
    page_title="Textile Costing Calculator",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---
@st.cache_data(ttl=60) # Cache defaults for a minute
def fetch_defaults():
    """Fetch default values from the API."""
    try:
        response = requests.get(f"{API_BASE_URL}/defaults")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to API: {e}")
        return None

def calculate_cost(materials, global_params):
    """Send calculation request to the API."""
    payload = {
        "materials": materials,
        "global_params": global_params
    }
    try:
        response = requests.post(f"{API_BASE_URL}/calculate", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Calculation API Error: {e}")
        if response.text:
             st.error(f"API Response Details: {response.text}")
        return None

def fetch_health():
     """Check API Health"""
     try:
         response = requests.get(f"{API_BASE_URL}/health")
         return response.status_code == 200
     except:
         return False

# --- Main UI ---
st.title("🧮 Textile Costing Calculator")
st.markdown("Calculate textile manufacturing costs using the LangGraph pipeline.")

# Check API connection
if not fetch_health():
    st.error("⚠️ Cannot connect to the FastAPI backend. Please ensure it is running on `http://127.0.0.1:8000`.")
    st.stop()

# Load Defaults
defaults = fetch_defaults()
if not defaults:
    st.stop()

# --- Sidebar: Global Parameters ---
with st.sidebar:
    st.header("⚙️ Global Parameters")
    
    global_params_defaults = defaults.get("global_params", {})
    
    saree_cut = st.number_input("Saree Cut (K26)", value=float(global_params_defaults.get("saree_cut", 6.6)), step=0.1)
    job_rate_k24 = st.number_input("Job Rate (K24)", value=float(global_params_defaults.get("job_rate_k24", 0.25)), step=0.01)
    job_rate_m8 = st.number_input("Job Rate (M8)", value=float(global_params_defaults.get("job_rate_m8", 0.28)), step=0.01)
    saree_cut_m7 = st.number_input("Saree Cut M7", value=float(global_params_defaults.get("saree_cut_m7", 6.2)), step=0.1)
    total_card = st.number_input("Total Card (O8)", value=float(global_params_defaults.get("total_card", 19649.0)), step=100.0)
    basic_rate = st.number_input("Basic Rate (A28)", value=float(global_params_defaults.get("basic_rate", 200.0)), step=10.0)
    gst_percent = st.number_input("GST % (B28)", value=float(global_params_defaults.get("gst_percent", 18.0)), step=1.0)
    pick = st.number_input("Pick (A24)", value=float(global_params_defaults.get("pick", 7.0)), step=0.1)
    work = st.number_input("Work (B24)", value=float(global_params_defaults.get("work", 4.3)), step=0.1)
    cut = st.number_input("Cut (C24)", value=float(global_params_defaults.get("cut", 6.3)), step=0.1)

    global_params = {
        "saree_cut": saree_cut,
        "job_rate_k24": job_rate_k24,
        "job_rate_m8": job_rate_m8,
        "saree_cut_m7": saree_cut_m7,
        "total_card": total_card,
        "basic_rate": basic_rate,
        "gst_percent": gst_percent,
        "pick": pick,
        "work": work,
        "cut": cut
    }

# --- Main Area: Material Inputs ---
st.header("🧵 Material Inputs")

default_materials = defaults.get("materials", [])
materials_input = []

# Create tabs for better organization if there are many materials, or expanders
num_materials_to_show = st.slider("Number of Materials to calculate", min_value=1, max_value=7, value=len(default_materials))

# Using columns for material inputs
cols = st.columns(3)

for i in range(num_materials_to_show):
    # Get default values for this index if available, else empty/default values
    mat_def = default_materials[i] if i < len(default_materials) else {
        "material_name": f"Material {i+1}", 
        "beam_tar": 0.0, 
        "denier": 0.0, 
        "rate": 0.0, 
        "has_e_multiplier": True
    }
    
    col_idx = i % 3
    with cols[col_idx]:
        with st.container(border=True):
            st.subheader(mat_def.get("material_name", f"Material {i+1}"))
            
            # Use columns inside the container for compact layout
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input(f"Name", value=mat_def.get("material_name"), key=f"name_{i}")
                beam_tar = st.number_input(f"Beam Tar", value=float(mat_def.get("beam_tar", 0)), step=10.0, key=f"bt_{i}")
            with c2:
                denier = st.number_input(f"Denier", value=float(mat_def.get("denier", 0)), step=10.0, key=f"den_{i}")
                rate = st.number_input(f"Rate", value=float(mat_def.get("rate", 0)), step=10.0, key=f"rate_{i}")
            
            has_e_multi = st.checkbox(
                "Has E Multiplier (4-param)", 
                value=mat_def.get("has_e_multiplier", True), 
                key=f"e_mult_{i}",
                help="False for Warp (3-param), True for others (4-param)"
            )
            
            materials_input.append({
                "material_name": name,
                "beam_tar": beam_tar,
                "denier": denier,
                "rate": rate,
                "has_e_multiplier": has_e_multi
            })

st.divider()

# --- Calculate Button ---
if st.button("🚀 Calculate Cost", type="primary", use_container_width=True):
    with st.spinner("Calculating via LangGraph pipeline..."):
        results = calculate_cost(materials_input, global_params)
        
        if results:
            st.success(f"✅ Calculation completed in {results.get('execution_time_ms', 0)} ms")
            
            # --- Results Display ---
            st.header("📊 Results")
            
            # 1. Top Level Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Final Cost (K27)", f"₹ {results.get('cost', 0):.2f}")
            m2.metric("Total Yarn + Job (N11)", f"₹ {results.get('total_yarn_job', 0):.2f}")
            m3.metric("Net Rate w/ GST (C28)", f"₹ {results.get('net_rate', 0):.2f}")
            m4.metric("Total Job (N9)", f"₹ {results.get('total_job', 0):.2f}")
            
            st.divider()
            
            # 2. Material Details Table
            st.subheader("🧵 Material Breakdown")
            if "materials" in results:
                df_materials = pd.DataFrame(results["materials"])
                # Formatting columns for display
                display_cols = ['material_name', 'beam_tar', 'denier', 'rate', 'ans', 'amt', 'yarn_weight', 'yarn_price']
                st.dataframe(
                    df_materials[display_cols].style.format({
                        'beam_tar': "{:.2f}",
                        'denier': "{:.2f}",
                        'rate': "₹ {:.2f}",
                        'ans': "{:.4f}",
                        'amt': "{:.4f}",
                        'yarn_weight': "{:.4f} kg",
                        'yarn_price': "₹ {:.2f}"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            
            st.divider()
            
            # 3. Secondary Metrics / Aggregations
            st.subheader("📈 Aggregated Totals")
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Total Pick (H26)", f"{results.get('total_pick', 0):.2f}")
            a2.metric("Sum Amt (I21)", f"{results.get('sum_amt', 0):.2f}")
            a3.metric("Total Amt Yarn (M24)", f"₹ {results.get('total_amt_yarn', 0):.2f}")
            a4.metric("Work Ratio (B26)", f"{results.get('work_ratio', 0):.4f}")
            
            # Optional: Show execution trace
            with st.expander("🛠️ Workflow Execution Trace"):
                st.write("Nodes executed:")
                for i, node in enumerate(results.get("workflow_nodes_executed", [])):
                    st.write(f"{i+1}. `{node}`")
