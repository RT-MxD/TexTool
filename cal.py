"""
Textile Costing Calculator - LangGraph Workflow
================================================
Complete implementation replicating ALL formulas from the Excel spreadsheet.
Processes 10 materials (Warp + 9 user-named materials) through a
multi-stage calculation pipeline -> TOTAL JOB, TOTAL AMT YARN, COST.

LangGraph Workflow Stages:
  START -> calculate_ans -> calculate_amt -> calculate_yarn_weight
        -> calculate_yarn_price -> aggregate_totals -> calculate_job -> calculate_cost -> END
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END   
import json


# ──────────────────────── State Definitions ────────────────────────

class MaterialData(TypedDict):
    """Represents a single material (Warp + 9 user-named materials)."""
    material_name: str
    denier: float       # Column B - Denier (user input)
    peak: float           # Column C - Peak (user input)
    panno: float         # Column D - Panno (user input)
    multiplier_e: float   # Column E - fixed value (100), Warp uses only D
    rate: float           # Column H - Rate (user input)
    has_e_multiplier: bool  # Warp uses 3-param formula, rest use 4-param
    # Calculated fields
    ans: float            # Column G (same row) - Ans
    amt: float            # Column G (next row) - Amt = Ans * Rate
    yarn_weight: float    # Column I - Yarn Weight
    yarn_price: float     # Column J - Yarn Price


class CostingState(TypedDict):
    """Complete state flowing through the LangGraph workflow."""
    # -- User Inputs --
    materials: List[MaterialData]
    saree_cut: float       # K26 - Saree Cut
    job_rate_k24: float    # K24 - Job Rate (0.25)
    job_rate_m8: float     # M8  - Job Rate (0.28)
    saree_cut_m7: float    # M7  - Saree Cut for job calc (6.2)
    total_card: float      # O8  - Total Card
    divisor: float         # Divisor for Ans calculation (user input, e.g. 9000000)

    # -- Calculated Values --
    total_pick: float      # H26 = Sum of all peak
    sum_amt: float         # I21 = Sum of all Amt values
    j21: float             # J21 = I21 / 100
    j22: float             # J22 = H26 * K24
    j23: float             # J23 = J21 + J22
    total_amt_yarn: float  # M24 = Sum of all Rates
    n6: float              # N6  = J3 + J6 + J9 (top 3 Rates)
    n8: float              # N8  = H26 * M8
    total_job_n9: float    # N9  = N8 * M7
    total_job_l24: float   # L24 = J22 * K26
    total_yarn_job: float  # N11 = N9 + N6
    cost: float            # K27 = J23 * K26 (FINAL COST)


# ──────────────────────── Node Functions ────────────────────────

def calculate_ans(state: CostingState) -> Dict[str, Any]:
    """
    Node 1: Calculate 'Ans' for each material (Column G).
    
    Warp formula:   G3 = B3 * C3 * D3 / divisor
    Others formula: G6 = B6 * C6 * D6 * E6 / divisor
    """
    materials = state.get("materials", [])
    divisor = state.get("divisor", 9_000_000.0)
    updated = []

    for mat in materials:
        new_mat = dict(mat)
        if mat["has_e_multiplier"]:
            # 4-parameter formula: B * C * D * E / divisor
            new_mat["ans"] = (
                mat["denier"] * mat["peak"] * 
                mat["panno"] * mat["multiplier_e"]
            ) / divisor
        else:
            # 3-parameter formula (Warp only): B * C * D / divisor
            new_mat["ans"] = (
                mat["denier"] * mat["peak"] * mat["panno"]
            ) / divisor
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
    
    H26 = Sum of peak values (excluding Warp) (Total Pick)
    I21 = Sum of all Amt values
    J21 = I21 / 100
    N6  = J3 + J6 + J9 (top 3 materials' Rates)
    M24 = Sum of all Rates (TOTAL AMT YARN)
    """
    materials = state.get("materials", [])

    # H26: Total Pick = sum of peak values (excluding the first material, which is Warp)
    total_pick = sum(mat["peak"] for mat in materials[1:]) if len(materials) > 1 else 0.0

    # I21: Sum of all Amt
    sum_amt = sum(mat["amt"] for mat in materials)

    # J21 = I21 / 100
    j21 = sum_amt / 100

    # N6: Sum of top 3 materials' Rates (Warp + Lichi + Shampen)
    n6 = sum(mat["yarn_price"] for mat in materials[:3])

    # M24: Total Amt Yarn = sum of all Rates
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
    Node 7: Calculate FINAL COST.
    
    K27 = J23 * K26 (COST - Final Output!)
    """
    j23 = state.get("j23", 0.0)
    saree_cut = state.get("saree_cut", 0.0)

    # K27: FINAL COST
    cost = j23 * saree_cut

    return {
        "cost": cost,
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
    denier: float,
    peak: float,
    panno: float,
    rate: float,
    multiplier_e: float = 100.0,
    has_e_multiplier: bool = True,
) -> MaterialData:
    """Factory function to create a MaterialData entry."""
    return MaterialData(
        material_name=name,
        denier=denier,
        peak=peak,
        panno=panno,
        multiplier_e=multiplier_e,
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
    print("  \U0001f9ee TEXTILE COSTING CALCULATOR")
    print("  LangGraph Workflow Engine")
    print("=" * 60)

    # Global inputs
    print("\n\u2500\u2500 Global Parameters \u2500\u2500")
    saree_cut = float(input("  Saree Cut (K26) [default 6.6]: ") or "6.6")
    job_rate_k24 = float(input("  Job Rate K24 [default 0.25]: ") or "0.25")
    job_rate_m8 = float(input("  Job Rate M8  [default 0.28]: ") or "0.28")
    saree_cut_m7 = float(input("  Saree Cut M7 [default 6.2]: ") or "6.2")
    total_card = float(input("  Total Card O8 [default 19649]: ") or "19649")
    divisor = float(input("  Divisor for Ans calculation [default 9000000]: ") or "9000000")

    materials = []

    # Material 1: Warp (fixed name)
    print("\n\u2500\u2500 Warp (Fixed) \u2500\u2500")
    warp_beam_tar = float(input("  Denier (B) [default 110]: ") or "110")
    warp_peak = float(input("  Peak (C) [default 110]: ") or "110")
    warp_denier = float(input("  Panno (D) [default 110]: ") or "110")
    warp_rate = float(input("  Rate (H) [default 325]: ") or "325")
    materials.append(create_material(
        name="Warp",
        denier=warp_beam_tar,
        peak=warp_peak,
        panno=warp_denier,
        rate=warp_rate,
        has_e_multiplier=False,
    ))

    # Materials 2-10: User-named materials
    for i in range(2, 11):
        print(f"\n\u2500\u2500 Material {i} of 10 \u2500\u2500")
        mat_name = input(f"  Material Name [default Material-{i}]: ") or f"Material-{i}"
        denier = float(input(f"  Denier (B) [default 0]: ") or "0")
        peak = float(input(f"  Peak (C) [default 0]: ") or "0")
        panno = float(input(f"  Panno (D) [default 0]: ") or "0")
        rate = float(input(f"  Rate (H) [default 0]: ") or "0")

        materials.append(create_material(
            name=mat_name,
            denier=denier,
            peak=peak,
            panno=panno,
            rate=rate,
            has_e_multiplier=True,
        ))

    return CostingState(
        materials=materials,
        saree_cut=saree_cut,
        job_rate_k24=job_rate_k24,
        job_rate_m8=job_rate_m8,
        saree_cut_m7=saree_cut_m7,
        total_card=total_card,
        divisor=divisor,
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
    )


def print_results(state: Dict[str, Any]):
    """Pretty-print the final calculated results."""
    print("\n" + "=" * 60)
    print("  \U0001f4ca CALCULATION RESULTS")
    print("=" * 60)

    # Per-material results
    print("\n\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510")
    print("\u2502 Material      \u2502   Ans    \u2502   Amt    \u2502 Yarn Wt  \u2502Yarn Price\u2502")
    print("\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524")
    for mat in state["materials"]:
        print(f"\u2502 {mat['material_name']:<13} \u2502 {mat['ans']:>8.2f} \u2502 {mat['amt']:>8.2f} \u2502 {mat['yarn_weight']:>8.4f} \u2502 {mat['yarn_price']:>8.2f} \u2502")
    print("\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")

    # Aggregation results
    print(f"\n  Total Pick (H26):        {state['total_pick']:.2f}")
    print(f"  Sum Amt (I21):           {state['sum_amt']:.2f}")
    print(f"  J21 (I21/100):           {state['j21']:.2f}")
    print(f"  J22 (Pick \u00d7 JobRate):    {state['j22']:.2f}")
    print(f"  J23 (J21 + J22):         {state['j23']:.2f}")

    print(f"\n  \u2500\u2500\u2500 FINAL OUTPUTS \u2500\u2500\u2500")
    print(f"  TOTAL JOB  (N9):         {state['total_job_n9']:.2f}")
    print(f"  TOTAL JOB  (L24):        {state['total_job_l24']:.2f}")
    print(f"  TOTAL AMT YARN (M24):    {state['total_amt_yarn']:.2f}")
    print(f"  TOTAL YARN+JOB (N11):    {state['total_yarn_job']:.2f}")

    print(f"\n  \u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557")
    print(f"  \u2551   \U0001f4b0 COST (K27): {state['cost']:>12.2f}   \u2551")
    print(f"  \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d")


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
