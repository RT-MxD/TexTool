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
    
    def_saree_cut = float(global_params_defaults.get("saree_cut", 6.6))
    saree_cut_in = st.number_input("Saree Cut (K26)", value=None, placeholder=str(def_saree_cut), step=0.1)
    saree_cut = saree_cut_in if saree_cut_in is not None else def_saree_cut
    def_job_k24 = float(global_params_defaults.get("job_rate_k24", 0.25))
    job_rate_k24_in = st.number_input("Job Rate (K24)", value=None, placeholder=str(def_job_k24), step=0.01)
    job_rate_k24 = job_rate_k24_in if job_rate_k24_in is not None else def_job_k24
    def_job_m8 = float(global_params_defaults.get("job_rate_m8", 0.28))
    job_rate_m8_in = st.number_input("Job Rate (M8)", value=None, placeholder=str(def_job_m8), step=0.01)
    job_rate_m8 = job_rate_m8_in if job_rate_m8_in is not None else def_job_m8
    def_saree_m7 = float(global_params_defaults.get("saree_cut_m7", 6.2))
    saree_cut_m7_in = st.number_input("Saree Cut M7", value=None, placeholder=str(def_saree_m7), step=0.1)
    saree_cut_m7 = saree_cut_m7_in if saree_cut_m7_in is not None else def_saree_m7
    def_total_card = float(global_params_defaults.get("total_card", 19649.0))
    total_card_in = st.number_input("Total Card (O8)", value=None, placeholder=str(def_total_card), step=100.0)
    total_card = total_card_in if total_card_in is not None else def_total_card
    def_divisor = float(global_params_defaults.get("divisor", 9000000.0))
    divisor_in = st.number_input("Divisor for Ans Calculation", value=None, placeholder=str(def_divisor), step=100000.0)
    divisor = divisor_in if divisor_in is not None else def_divisor

    global_params = {
        "saree_cut": saree_cut,
        "job_rate_k24": job_rate_k24,
        "job_rate_m8": job_rate_m8,
        "saree_cut_m7": saree_cut_m7,
        "total_card": total_card,
        "divisor": divisor,
    }

# --- Main Area: Material Inputs ---
st.header("🧵 Material Inputs")

default_materials = defaults.get("materials", [])
materials_input = []

# Create pills for better organization to select number of materials
num_options = list(range(1, 11))
num_materials_to_show = st.pills(
    "Number of Materials to calculate", 
    options=num_options, 
    default=len(default_materials) if len(default_materials) in num_options else 1
)
if not num_materials_to_show:
    num_materials_to_show = len(default_materials) if len(default_materials) in num_options else 1

# Using columns for material inputs
cols = st.columns(3)

for i in range(num_materials_to_show):
    # Get default values for this index if available, else empty/default values
    mat_def = default_materials[i] if i < len(default_materials) else {
        "material_name": f"Material-{i+1}", 
        "beam_tar": 0.0,
        "peak": 0.0,
        "denier": 0.0, 
        "rate": 0.0, 
        "has_e_multiplier": True
    }
    
    col_idx = i % 3
    with cols[col_idx]:
        with st.container(border=True):
            st.subheader(mat_def.get("material_name", f"Material-{i+1}"))
            
            # Use columns inside the container for compact layout
            c1, c2 = st.columns(2)
            with c1:
                def_name = mat_def.get("material_name")
                name_in = st.text_input(f"Name", value="", placeholder=def_name, key=f"name_{i}")
                name = name_in if name_in != "" else def_name
                def_bt = float(mat_def.get("beam_tar", 0))
                beam_tar_in = st.number_input(f"Beam Tar", value=None, placeholder=str(def_bt), step=10.0, key=f"bt_{i}")
                beam_tar = beam_tar_in if beam_tar_in is not None else def_bt
                def_peak = float(mat_def.get("peak", 0))
                peak_in = st.number_input(f"Peak", value=None, placeholder=str(def_peak), step=10.0, key=f"peak_{i}")
                peak = peak_in if peak_in is not None else def_peak
            with c2:
                def_den = float(mat_def.get("denier", 0))
                denier_in = st.number_input(f"Denier", value=None, placeholder=str(def_den), step=10.0, key=f"den_{i}")
                denier = denier_in if denier_in is not None else def_den
                def_rate = float(mat_def.get("rate", 0))
                rate_in = st.number_input(f"Rate", value=None, placeholder=str(def_rate), step=10.0, key=f"rate_{i}")
                rate = rate_in if rate_in is not None else def_rate
            
            has_e_multi = st.checkbox(
                "Has E Multiplier (4-param)", 
                value=mat_def.get("has_e_multiplier", True), 
                key=f"e_mult_{i}",
                help="False for Warp (3-param), True for others (4-param)"
            )
            
            materials_input.append({
                "material_name": name,
                "beam_tar": beam_tar,
                "peak": peak,
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
            m1, m2, m3 = st.columns(3)
            m1.metric("Final Cost (K27)", f"₹ {results.get('cost', 0):.2f}")
            m2.metric("Total Job (L24)", f"₹ {results.get('total_job_alt', 0):.2f}")
            m3.metric("Total Amt Yarn (M24)", f"₹ {results.get('total_amt_yarn', 0):.2f}")
            
            st.divider()
            
            # 2. Material Details Table
            st.subheader("🧵 Material Breakdown")
            if "materials" in results:
                df_materials = pd.DataFrame(results["materials"])
                # Formatting columns for display
                display_cols = ['material_name', 'beam_tar', 'peak', 'denier', 'rate', 'ans', 'amt', 'yarn_weight', 'yarn_price']
                st.dataframe(
                    df_materials[display_cols].style.format({
                        'beam_tar': "{:.2f}",
                        'peak': "{:.2f}",
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
            a1, a2, a3 = st.columns(3)
            a1.metric("Total Pick (H26)", f"{results.get('total_pick', 0):.2f}")
            a2.metric("Sum Amt (I21)", f"{results.get('sum_amt', 0):.2f}")
            a3.metric("Total Amt Yarn (N6)", f"₹ {results.get('n6', 0):.2f}")
            
            
            b1, b2 = st.columns(2)
            b1.metric("Total Job (N9)", f"₹ {results.get('total_job', 0):.2f}")
            b2.metric("Total Yarn + Job (N11)", f"₹ {results.get('total_yarn_job', 0):.2f}")
            
            # Optional: Show execution trace
            with st.expander("🛠️ Workflow Execution Trace"):
                st.write("Nodes executed:")
                for i, node in enumerate(results.get("workflow_nodes_executed", [])):
                    st.write(f"{i+1}. `{node}`")
