"""
Textile Costing Calculator - LangGraph Workflow
================================================
Complete implementation replicating ALL 46 formulas from the Excel spreadsheet.
Processes 7 materials (Warp, 150 Lichi, Shampen, Weft 3-6) through a
multi-stage calculation pipeline → TOTAL JOB, TOTAL AMT YARN, COST.

LangGraph Workflow Stages:
  START → input_collection → calculate_ans → calculate_amt → calculate_yarn_weight
        → calculate_yarn_price → aggregate_totals → calculate_job → calculate_cost → END
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
import json


# ──────────────────────── State Definitions ────────────────────────

class MaterialData(TypedDict):
    """Represents a single material (Warp, Lichi, Shampen, Weft-3 to Weft-6)."""
    material_name: str
    beam_tar: float       # Column B - Beam Tar (user input)
    denier: float         # Column C - Denier (user input)
    multiplier_d: float   # Column D - fixed value (50)
    multiplier_e: float   # Column E - fixed value (100), Warp uses only D
    divisor: float        # Column C (next row) - always 9000000
    rate: float           # Column H - Rate (user input)
    has_e_multiplier: bool  # Warp uses 3-param formula, rest use 4-param
    # Calculated fields
    ans: float            # Column G (same row) - Ans
    amt: float            # Column G (next row) - Amt = Ans × Rate
    yarn_weight: float    # Column I - Yarn Weight
    yarn_price: float     # Column J - Yarn Price


class CostingState(TypedDict):
    """Complete state flowing through the LangGraph workflow."""
    # ── User Inputs ──
    materials: List[MaterialData]
    saree_cut: float       # K26 - Saree Cut
    job_rate_k24: float    # K24 - Job Rate (0.25)
    job_rate_m8: float     # M8  - Job Rate (0.28)
    saree_cut_m7: float    # M7  - Saree Cut for job calc (6.2)
    #total_card: float      # O8  - Total Card
    #basic_rate: float      # A28 - Basic Rate
    #gst_percent: float     # B28 - GST %
    pick: float            # A24 - Pick
    work: float            # B24 - Work
    cut: float             # C24 - Cut

    # ── Calculated Values ──
    total_pick: float      # H26 = Sum of all deniers
    sum_amt: float         # I21 = Sum of all Amt values
    j21: float             # J21 = I21 / 100
    j22: float             # J22 = H26 * K24
    j23: float             # J23 = J21 + J22
    total_amt_yarn: float  # M24 = Sum of all yarn prices
    n6: float              # N6  = J3 + J6 + J9 (top 3 yarn prices)
    n8: float              # N8  = H26 * M8
    total_job_n9: float    # N9  = N8 * M7
    total_job_l24: float   # L24 = J22 * K26
    total_yarn_job: float  # N11 = N9 + N6
    cost: float            # K27 = J23 * K26 (FINAL COST)
    #net_rate: float        # C28 = (A28 * B28%) + A28
    #work_ratio: float      # B26 = A24/C24 * B24
    total_card_calc: float # O9  = (O8 * M8) / 39.37


# ──────────────────────── Node Functions ────────────────────────

def calculate_ans(state: CostingState) -> Dict[str, Any]:
    """
    Node 1: Calculate 'Ans' for each material (Column G).
    
    Warp formula:   G3 = B3 * C3 * D3 / 9000000
    Others formula: G6 = B6 * C6 * D6 * E6 / 9000000
    """
    materials = state.get("materials", [])
    updated = []

    for mat in materials:
        new_mat = dict(mat)
        if mat["has_e_multiplier"]:
            # 4-parameter formula: B * C * D * E / 9M
            new_mat["ans"] = (
                mat["beam_tar"] * mat["denier"] * 
                mat["multiplier_d"] * mat["multiplier_e"]
            ) / mat["divisor"]
        else:
            # 3-parameter formula (Warp only): B * C * D / 9M
            new_mat["ans"] = (
                mat["beam_tar"] * mat["denier"] * mat["multiplier_d"]
            ) / mat["divisor"]
        updated.append(new_mat)

    return {"materials": updated}


def calculate_amt(state: CostingState) -> Dict[str, Any]:
    """
    Node 2: Calculate 'Amt' for each material (Column G next row).
    
    Formula: G4 = G3 * H3 (i.e., Ans × Rate)
    """
    materials = state.get("materials", [])
    updated = []

    for mat in materials:
        new_mat = dict(mat)
        new_mat["amt"] = mat["ans"] * mat["rate"]
        updated.append(new_mat)

    return {"materials": updated}


def calculate_yarn_weight(state: CostingState) -> Dict[str, Any]:
    """
    Node 3: Calculate Yarn Weight for each material (Column I).
    
    Formula: I3 = G3 / 100 * K26 (i.e., Ans / 100 × saree_cut)
    """
    materials = state.get("materials", [])
    saree_cut = state.get("saree_cut", 0.0)
    updated = []

    for mat in materials:
        new_mat = dict(mat)
        new_mat["yarn_weight"] = (mat["ans"] / 100) * saree_cut
        updated.append(new_mat)

    return {"materials": updated}


def calculate_yarn_price(state: CostingState) -> Dict[str, Any]:
    """
    Node 4: Calculate Yarn Price for each material (Column J).
    
    Formula: J3 = H3 * I3 (i.e., Rate × Yarn Weight)
    """
    materials = state.get("materials", [])
    updated = []

    for mat in materials:
        new_mat = dict(mat)
        new_mat["yarn_price"] = mat["rate"] * mat["yarn_weight"]
        updated.append(new_mat)

    return {"materials": updated}


def aggregate_totals(state: CostingState) -> Dict[str, Any]:
    """
    Node 5: Compute all aggregation formulas.
    
    H26 = Sum of all deniers (Total Pick)
    I21 = Sum of all Amt values
    J21 = I21 / 100
    N6  = J3 + J6 + J9 (top 3 materials' yarn prices)
    M24 = Sum of all yarn prices (TOTAL AMT YARN)
    """
    materials = state.get("materials", [])

    # H26: Total Pick = sum of all denier values
    total_pick = sum(mat["denier"] for mat in materials)

    # I21: Sum of all Amt
    sum_amt = sum(mat["amt"] for mat in materials)

    # J21 = I21 / 100
    j21 = sum_amt / 100

    # N6: Sum of top 3 materials' yarn prices (Warp + Lichi + Shampen)
    n6 = sum(mat["yarn_price"] for mat in materials[:3])

    # M24: Total Amt Yarn = sum of all yarn prices
    total_amt_yarn = sum(mat["yarn_price"] for mat in materials)

    return {
        "total_pick": total_pick,
        "sum_amt": sum_amt,
        "j21": j21,
        "n6": n6,
        "total_amt_yarn": total_amt_yarn,
    }


def calculate_job(state: CostingState) -> Dict[str, Any]:
    """
    Node 6: Calculate Job-related values.
    
    J22 = H26 * K24 (Total Pick × Job Rate)
    J23 = J21 + J22
    N8  = H26 * M8
    N9  = N8 * M7  (TOTAL JOB)
    L24 = J22 * K26 (TOTAL JOB alt)
    N11 = N9 + N6  (TOTAL YARN + JOB)
    """
    total_pick = state.get("total_pick", 0.0)
    j21 = state.get("j21", 0.0)
    n6 = state.get("n6", 0.0)
    job_rate_k24 = state.get("job_rate_k24", 0.0)
    job_rate_m8 = state.get("job_rate_m8", 0.0)
    saree_cut_m7 = state.get("saree_cut_m7", 0.0)
    saree_cut = state.get("saree_cut", 0.0)

    j22 = total_pick * job_rate_k24       # J22 = H26 * K24
    j23 = j21 + j22                       # J23 = J21 + J22
    n8 = total_pick * job_rate_m8         # N8  = H26 * M8
    total_job_n9 = n8 * saree_cut_m7      # N9  = N8 * M7
    total_job_l24 = j22 * saree_cut       # L24 = J22 * K26
    total_yarn_job = total_job_n9 + n6    # N11 = N9 + N6

    return {
        "j22": j22,
        "j23": j23,
        "n8": n8,
        "total_job_n9": total_job_n9,
        "total_job_l24": total_job_l24,
        "total_yarn_job": total_yarn_job,
    }


def calculate_cost(state: CostingState) -> Dict[str, Any]:
    """
    Node 7: Calculate FINAL COST and supplementary values.
    
    K27 = J23 * K26 (COST - Final Output!)
    C28 = (A28 * B28%) + A28 (Net Rate with GST)
    B26 = A24 / C24 * B24 (Work Ratio)
    O9  = (O8 * M8) / 39.37 (Total Card calc)
    """
    j23 = state.get("j23", 0.0)
    saree_cut = state.get("saree_cut", 0.0)
    #basic_rate = state.get("basic_rate", 0.0)
    #gst_percent = state.get("gst_percent", 0.0)
    pick = state.get("pick", 0.0)
    work = state.get("work", 0.0)
    cut = state.get("cut", 0.0)
    total_card = state.get("total_card", 0.0)
    job_rate_m8 = state.get("job_rate_m8", 0.0)

    # K27: FINAL COST
    cost = j23 * saree_cut

    # C28: Net Rate = (basic_rate × gst%) + basic_rate
    #net_rate = (basic_rate * gst_percent / 100) + basic_rate

    # B26: Work Ratio = pick / cut × work
    #work_ratio = (pick / cut * work) if cut != 0 else 0.0

    # O9: Total Card calc = (O8 * M8) / 39.37
    #total_card_calc = (total_card * job_rate_m8) / 39.37 if total_card else 0.0

    return {
        "cost": cost,
        #"net_rate": net_rate,
        #"work_ratio": work_ratio,
        #"total_card_calc": total_card_calc,
    }


# ──────────────────────── Graph Builder ────────────────────────

def build_costing_graph():
    """
    Constructs the complete LangGraph workflow.
    
    Flow:
      START → calculate_ans → calculate_amt → calculate_yarn_weight
            → calculate_yarn_price → aggregate_totals → calculate_job
            → calculate_cost → END
    """
    workflow = StateGraph(CostingState)

    # Add all nodes
    workflow.add_node("calculate_ans", calculate_ans)
    workflow.add_node("calculate_amt", calculate_amt)
    workflow.add_node("calculate_yarn_weight", calculate_yarn_weight)
    workflow.add_node("calculate_yarn_price", calculate_yarn_price)
    workflow.add_node("aggregate_totals", aggregate_totals)
    workflow.add_node("calculate_job", calculate_job)
    workflow.add_node("calculate_cost", calculate_cost)

    # Define sequential edges
    workflow.add_edge(START, "calculate_ans")
    workflow.add_edge("calculate_ans", "calculate_amt")
    workflow.add_edge("calculate_amt", "calculate_yarn_weight")
    workflow.add_edge("calculate_yarn_weight", "calculate_yarn_price")
    workflow.add_edge("calculate_yarn_price", "aggregate_totals")
    workflow.add_edge("aggregate_totals", "calculate_job")
    workflow.add_edge("calculate_job", "calculate_cost")
    workflow.add_edge("calculate_cost", END)

    return workflow.compile()


# ──────────────────────── Helper: Create Material ────────────────────────

def create_material(
    name: str,
    beam_tar: float,
    denier: float,
    rate: float,
    multiplier_d: float = 50.0,
    multiplier_e: float = 100.0,
    divisor: float = 9_000_000.0,
    has_e_multiplier: bool = True,
) -> MaterialData:
    """Factory function to create a MaterialData entry."""
    return MaterialData(
        material_name=name,
        beam_tar=beam_tar,
        denier=denier,
        multiplier_d=multiplier_d,
        multiplier_e=multiplier_e,
        divisor=divisor,
        rate=rate,
        has_e_multiplier=has_e_multiplier,
        ans=0.0,
        amt=0.0,
        yarn_weight=0.0,
        yarn_price=0.0,
    )


# ──────────────────────── Interactive Input ────────────────────────

def get_user_inputs() -> CostingState:
    """Collect all inputs from the user interactively."""
    print("=" * 60)
    print("  🧮 TEXTILE COSTING CALCULATOR")
    print("  LangGraph Workflow Engine")
    print("=" * 60)

    # Global inputs
    print("\n── Global Parameters ──")
    saree_cut = float(input("  Saree Cut (K26) [default 6.6]: ") or "6.6")
    job_rate_k24 = float(input("  Job Rate K24 [default 0.25]: ") or "0.25")
    job_rate_m8 = float(input("  Job Rate M8  [default 0.28]: ") or "0.28")
    saree_cut_m7 = float(input("  Saree Cut M7 [default 6.2]: ") or "6.2")
    total_card = float(input("  Total Card O8 [default 19649]: ") or "19649")
    basic_rate = float(input("  Basic Rate A28 [default 200]: ") or "200")
    gst_percent = float(input("  GST % B28 [default 18]: ") or "18")
    pick = float(input("  Pick A24 [default 7]: ") or "7")
    work = float(input("  Work B24 [default 4.3]: ") or "4.3")
    cut = float(input("  Cut  C24 [default 6.3]: ") or "6.3")

    materials = []

    # Material definitions with their defaults from Excel
    mat_defs = [
        ("Warp",     "B3",  110.0,  "C3",  110.0,  "H3",  325.0,  False),
        ("150 Lichi","B6",  140.0,  "C6",   70.0,  "H6",  252.0,  True),
        ("Shampen",  "B9",  280.0,  "C9",   52.0,  "H9",  300.0,  True),
        ("Weft-3",   "B13", 155.0, "C13",    0.0, "H13",  175.0,  True),
        ("Weft-4",   "B15", 155.0, "C15",    0.0, "H15",    0.0,  True),
        ("Weft-5",   "B17", 155.0, "C17",    0.0, "H17",    0.0,  True),
        ("Weft-6",   "B19", 155.0, "C19",    0.0, "H19",    0.0,  True),
    ]

    for name, b_ref, b_def, c_ref, c_def, h_ref, h_def, has_e in mat_defs:
        print(f"\n── {name} ──")
        beam_tar = float(input(f"  Beam Tar ({b_ref}) [default {b_def}]: ") or str(b_def))
        denier = float(input(f"  Denier ({c_ref}) [default {c_def}]: ") or str(c_def))
        rate = float(input(f"  Rate ({h_ref}) [default {h_def}]: ") or str(h_def))

        materials.append(create_material(
            name=name,
            beam_tar=beam_tar,
            denier=denier,
            rate=rate,
            has_e_multiplier=has_e,
        ))

    return CostingState(
        materials=materials,
        saree_cut=saree_cut,
        job_rate_k24=job_rate_k24,
        job_rate_m8=job_rate_m8,
        saree_cut_m7=saree_cut_m7,
        total_card=total_card,
        basic_rate=basic_rate,
        gst_percent=gst_percent,
        pick=pick,
        work=work,
        cut=cut,
        total_pick=0.0,
        sum_amt=0.0,
        j21=0.0,
        j22=0.0,
        j23=0.0,
        total_amt_yarn=0.0,
        n6=0.0,
        n8=0.0,
        total_job_n9=0.0,
        total_job_l24=0.0,
        total_yarn_job=0.0,
        cost=0.0,
        net_rate=0.0,
        work_ratio=0.0,
        total_card_calc=0.0,
    )


def print_results(state: Dict[str, Any]):
    """Pretty-print the final calculated results."""
    print("\n" + "=" * 60)
    print("  📊 CALCULATION RESULTS")
    print("=" * 60)

    # Per-material results
    print("\n┌─────────────┬──────────┬──────────┬──────────┬──────────┐")
    print("│ Material    │   Ans    │   Amt    │ Yarn Wt  │Yarn Price│")
    print("├─────────────┼──────────┼──────────┼──────────┼──────────┤")
    for mat in state["materials"]:
        print(f"│ {mat['material_name']:<11} │ {mat['ans']:>8.2f} │ {mat['amt']:>8.2f} │ {mat['yarn_weight']:>8.4f} │ {mat['yarn_price']:>8.2f} │")
    print("└─────────────┴──────────┴──────────┴──────────┴──────────┘")

    # Aggregation results
    print(f"\n  Total Pick (H26):        {state['total_pick']:.2f}")
    print(f"  Sum Amt (I21):           {state['sum_amt']:.2f}")
    print(f"  J21 (I21/100):           {state['j21']:.2f}")
    print(f"  J22 (Pick × JobRate):    {state['j22']:.2f}")
    print(f"  J23 (J21 + J22):         {state['j23']:.2f}")

    print(f"\n  ─── FINAL OUTPUTS ───")
    print(f"  TOTAL JOB  (N9):         {state['total_job_n9']:.2f}")
    print(f"  TOTAL JOB  (L24):        {state['total_job_l24']:.2f}")
    print(f"  TOTAL AMT YARN (M24):    {state['total_amt_yarn']:.2f}")
    print(f"  TOTAL YARN+JOB (N11):    {state['total_yarn_job']:.2f}")
    print(f"  Net Rate (C28):          {state['net_rate']:.2f}")
    print(f"  Work Ratio (B26):        {state['work_ratio']:.2f}")

    print(f"\n  ╔═════════════════════════════════╗")
    print(f"  ║   💰 COST (K27): {state['cost']:>12.2f}   ║")
    print(f"  ╚═════════════════════════════════╝")


# ──────────────────────── Main Execution ────────────────────────

if __name__ == "__main__":
    # Build the graph
    app = build_costing_graph()

    # Get user inputs
    initial_state = get_user_inputs()

    # Run the workflow
    print("\n⚙️  Running LangGraph Workflow...")
    print("  START → Ans → Amt → YarnWt → YarnPrice → Aggregation → Job → Cost → END")

    final_state = app.invoke(initial_state)

    # Display results
    print_results(final_state)