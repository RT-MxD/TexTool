"""
Textile Costing Calculator - FastAPI Server
============================================
REST API wrapping the LangGraph costing pipeline.

Endpoints:
  POST /calculate          - Full calculation with all material inputs
  POST /calculate/quick    - Quick calc with just the 3 main materials
  GET  /defaults           - Get default values for all inputs
  GET  /health             - Health check
  GET  /workflow           - Get workflow node descriptions
  GET  /                   - Interactive API documentation redirect

Run:
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import time

from cal import (
    build_costing_graph,
    create_material,
    CostingState,
)

# ──────────────────────── Pydantic Models ────────────────────────

class MaterialInput(BaseModel):
    """Input for a single material."""
    material_name: str = Field(..., description="Name of the material (e.g., 'Warp', '150 Lichi')")
    beam_tar: float = Field(..., description="Beam Tar value (Column B)")
    denier: float = Field(..., description="Denier value (Column C)")
    rate: float = Field(..., description="Rate per unit (Column H)")
    has_e_multiplier: bool = Field(
        True,
        description="False for Warp (3-param: B*C*D/9M), True for others (4-param: B*C*D*E/9M)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "material_name": "150 Lichi",
                "beam_tar": 140.0,
                "denier": 70.0,
                "rate": 252.0,
                "has_e_multiplier": True,
            }
        }


class GlobalParams(BaseModel):
    """Global parameters for the calculation."""
    saree_cut: float = Field(6.6, description="Saree Cut (K26)")
    job_rate_k24: float = Field(0.25, description="Job Rate (K24)")
    job_rate_m8: float = Field(0.28, description="Job Rate (M8)")
    saree_cut_m7: float = Field(6.2, description="Saree Cut for job calc (M7)")
    total_card: float = Field(19649.0, description="Total Card (O8)")
    basic_rate: float = Field(200.0, description="Basic Rate (A28)")
    gst_percent: float = Field(18.0, description="GST Percentage (B28)")
    pick: float = Field(7.0, description="Pick (A24)")
    work: float = Field(4.3, description="Work (B24)")
    cut: float = Field(6.3, description="Cut (C24)")


class CalculationRequest(BaseModel):
    """Full calculation request with materials and global params."""
    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="List of materials (1-7). Order: Warp, 150 Lichi, Shampen, Weft-3 to Weft-6"
    )
    global_params: GlobalParams = Field(
        default_factory=GlobalParams,
        description="Global calculation parameters (all have defaults)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "materials": [
                    {"material_name": "Warp", "beam_tar": 110.0, "denier": 110.0, "rate": 325.0, "has_e_multiplier": False},
                    {"material_name": "150 Lichi", "beam_tar": 140.0, "denier": 70.0, "rate": 252.0, "has_e_multiplier": True},
                    {"material_name": "Shampen", "beam_tar": 280.0, "denier": 52.0, "rate": 300.0, "has_e_multiplier": True},
                ],
                "global_params": {
                    "saree_cut": 6.6,
                    "job_rate_k24": 0.25,
                    "job_rate_m8": 0.28,
                    "saree_cut_m7": 6.2,
                }
            }
        }


class QuickCalcRequest(BaseModel):
    """Simplified request — just beam_tar, denier, rate for the 3 main materials."""
    warp_beam_tar: float = Field(110.0, description="Warp Beam Tar (B3)")
    warp_denier: float = Field(110.0, description="Warp Denier (C3)")
    warp_rate: float = Field(325.0, description="Warp Rate (H3)")

    lichi_beam_tar: float = Field(140.0, description="150 Lichi Beam Tar (B6)")
    lichi_denier: float = Field(70.0, description="150 Lichi Denier (C6)")
    lichi_rate: float = Field(252.0, description="150 Lichi Rate (H6)")

    shampen_beam_tar: float = Field(280.0, description="Shampen Beam Tar (B9)")
    shampen_denier: float = Field(52.0, description="Shampen Denier (C9)")
    shampen_rate: float = Field(300.0, description="Shampen Rate (H9)")

    weft3_beam_tar: float = Field(155.0, description="Weft-3 Beam Tar (B13)")
    weft3_denier: float = Field(0.0, description="Weft-3 Denier (C13)")
    weft3_rate: float = Field(175.0, description="Weft-3 Rate (H13)")

    weft4_beam_tar: float = Field(155.0, description="Weft-4 Beam Tar (B15)")
    weft4_denier: float = Field(0.0, description="Weft-4 Denier (C15)")
    weft4_rate: float = Field(0.0, description="Weft-4 Rate (H15)")

    weft5_beam_tar: float = Field(155.0, description="Weft-5 Beam Tar (B17)")
    weft5_denier: float = Field(0.0, description="Weft-5 Denier (C17)")
    weft5_rate: float = Field(0.0, description="Weft-5 Rate (H17)")

    weft6_beam_tar: float = Field(155.0, description="Weft-6 Beam Tar (B19)")
    weft6_denier: float = Field(0.0, description="Weft-6 Denier (C19)")
    weft6_rate: float = Field(0.0, description="Weft-6 Rate (H19)")

    saree_cut: float = Field(6.6, description="Saree Cut (K26)")
    job_rate_k24: float = Field(0.25, description="Job Rate (K24)")
    job_rate_m8: float = Field(0.28, description="Job Rate (M8)")
    saree_cut_m7: float = Field(6.2, description="Saree Cut M7")


class MaterialResult(BaseModel):
    """Calculated result for a single material."""
    material_name: str
    beam_tar: float
    denier: float
    rate: float
    ans: float = Field(description="G column - Base calculation")
    amt: float = Field(description="G next row - Ans × Rate")
    yarn_weight: float = Field(description="I column - Ans/100 × Saree Cut")
    yarn_price: float = Field(description="J column - Rate × Yarn Weight")


class CalculationResponse(BaseModel):
    """Complete calculation response."""
    # Per-material results
    materials: List[MaterialResult]

    # Aggregation results
    total_pick: float = Field(description="H26 - Sum of all deniers")
    sum_amt: float = Field(description="I21 - Sum of all Amt values")
    j21: float = Field(description="J21 = I21/100")
    j22: float = Field(description="J22 = H26 × K24 (Pick × Job Rate)")
    j23: float = Field(description="J23 = J21 + J22")

    # Final outputs
    total_job: float = Field(description="N9 - TOTAL JOB")
    total_job_alt: float = Field(description="L24 - TOTAL JOB (alternative)")
    total_amt_yarn: float = Field(description="M24 - TOTAL AMT YARN")
    total_yarn_job: float = Field(description="N11 - TOTAL YARN + JOB")
    cost: float = Field(description="K27 - FINAL COST = J23 × Saree Cut")
    net_rate: float = Field(description="C28 - Net Rate with GST")
    work_ratio: float = Field(description="B26 - Work Ratio")

    # Metadata
    workflow_nodes_executed: List[str]
    execution_time_ms: float


# ──────────────────────── FastAPI App ────────────────────────

app = FastAPI(
    title="🧮 Textile Costing Calculator API",
    description="""
## LangGraph-Powered Textile Costing Pipeline

This API wraps a **LangGraph workflow** that replicates all **46 formulas** from the
textile costing Excel spreadsheet.

### Workflow Pipeline
```
START → calculate_ans → calculate_amt → calculate_yarn_weight
      → calculate_yarn_price → aggregate_totals → calculate_job
      → calculate_cost → END
```

### Materials Supported
- **Warp** (3-param formula: B×C×D / 9M)
- **150 Lichi** (4-param: B×C×D×E / 9M)
- **Shampen** (4-param)
- **Weft-3 through Weft-6** (4-param)

### Key Outputs
- **TOTAL JOB** (N9)
- **TOTAL AMT YARN** (M24)
- **COST** (K27) — Final output
    """,
    version="1.0.0",
    contact={"name": "Textile Calculator"},
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the LangGraph pipeline once at startup
costing_graph = build_costing_graph()

WORKFLOW_NODES = [
    "calculate_ans",
    "calculate_amt",
    "calculate_yarn_weight",
    "calculate_yarn_price",
    "aggregate_totals",
    "calculate_job",
    "calculate_cost",
]


# ──────────────────────── Helper Functions ────────────────────────

def build_initial_state(
    materials: List[MaterialInput],
    params: GlobalParams,
) -> CostingState:
    """Convert Pydantic models to LangGraph CostingState."""
    mat_list = []
    for m in materials:
        mat_list.append(create_material(
            name=m.material_name,
            beam_tar=m.beam_tar,
            denier=m.denier,
            rate=m.rate,
            has_e_multiplier=m.has_e_multiplier,
        ))

    return CostingState(
        materials=mat_list,
        saree_cut=params.saree_cut,
        job_rate_k24=params.job_rate_k24,
        job_rate_m8=params.job_rate_m8,
        saree_cut_m7=params.saree_cut_m7,
        total_card=params.total_card,
        basic_rate=params.basic_rate,
        gst_percent=params.gst_percent,
        pick=params.pick,
        work=params.work,
        cut=params.cut,
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


def format_response(result: dict, exec_time: float) -> CalculationResponse:
    """Convert LangGraph final state to API response."""
    material_results = []
    for mat in result["materials"]:
        material_results.append(MaterialResult(
            material_name=mat["material_name"],
            beam_tar=mat["beam_tar"],
            denier=mat["denier"],
            rate=mat["rate"],
            ans=round(mat["ans"], 4),
            amt=round(mat["amt"], 4),
            yarn_weight=round(mat["yarn_weight"], 6),
            yarn_price=round(mat["yarn_price"], 4),
        ))

    return CalculationResponse(
        materials=material_results,
        total_pick=round(result["total_pick"], 2),
        sum_amt=round(result["sum_amt"], 2),
        j21=round(result["j21"], 4),
        j22=round(result["j22"], 4),
        j23=round(result["j23"], 4),
        total_job=round(result["total_job_n9"], 4),
        total_job_alt=round(result["total_job_l24"], 4),
        total_amt_yarn=round(result["total_amt_yarn"], 4),
        total_yarn_job=round(result["total_yarn_job"], 4),
        cost=round(result["cost"], 4),
        net_rate=round(result["net_rate"], 2),
        work_ratio=round(result["work_ratio"], 4),
        workflow_nodes_executed=WORKFLOW_NODES,
        execution_time_ms=round(exec_time * 1000, 2),
    )


# ──────────────────────── API Endpoints ────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Redirect to interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Textile Costing Calculator",
        "pipeline": "LangGraph",
        "nodes": len(WORKFLOW_NODES),
        "workflow": " → ".join(["START"] + WORKFLOW_NODES + ["END"]),
    }


@app.get("/workflow", tags=["System"])
async def get_workflow():
    """Get detailed workflow node descriptions."""
    return {
        "pipeline": "LangGraph StateGraph",
        "total_formulas": 46,
        "nodes": [
            {
                "name": "calculate_ans",
                "stage": 1,
                "description": "Calculate base 'Ans' for each material",
                "formula_warp": "G = B × C × D / 9,000,000",
                "formula_others": "G = B × C × D × E / 9,000,000",
                "inputs": ["beam_tar (B)", "denier (C)", "multiplier_d (D=50)", "multiplier_e (E=100)"],
                "outputs": ["ans (G column)"],
            },
            {
                "name": "calculate_amt",
                "stage": 2,
                "description": "Calculate Amt = Ans × Rate for each material",
                "formula": "Amt = G × H",
                "inputs": ["ans (from stage 1)", "rate (H)"],
                "outputs": ["amt (G next row)"],
            },
            {
                "name": "calculate_yarn_weight",
                "stage": 3,
                "description": "Calculate Yarn Weight for each material",
                "formula": "I = G/100 × K26 (saree_cut)",
                "inputs": ["ans (from stage 1)", "saree_cut (K26)"],
                "outputs": ["yarn_weight (I column)"],
            },
            {
                "name": "calculate_yarn_price",
                "stage": 4,
                "description": "Calculate Yarn Price for each material",
                "formula": "J = H × I (rate × yarn_weight)",
                "inputs": ["rate (H)", "yarn_weight (from stage 3)"],
                "outputs": ["yarn_price (J column)"],
            },
            {
                "name": "aggregate_totals",
                "stage": 5,
                "description": "Sum up all per-material values",
                "formulas": {
                    "H26": "Sum of all deniers (Total Pick)",
                    "I21": "Sum of all Amt values",
                    "J21": "I21 / 100",
                    "N6": "J3 + J6 + J9 (top 3 yarn prices)",
                    "M24": "Sum of all yarn prices (TOTAL AMT YARN)",
                },
                "outputs": ["total_pick", "sum_amt", "j21", "n6", "total_amt_yarn"],
            },
            {
                "name": "calculate_job",
                "stage": 6,
                "description": "Calculate job-related totals",
                "formulas": {
                    "J22": "H26 × K24 (Total Pick × Job Rate)",
                    "J23": "J21 + J22",
                    "N8": "H26 × M8",
                    "N9": "N8 × M7 (TOTAL JOB)",
                    "L24": "J22 × K26 (TOTAL JOB alt)",
                    "N11": "N9 + N6 (TOTAL YARN + JOB)",
                },
                "outputs": ["j22", "j23", "total_job_n9", "total_job_l24", "total_yarn_job"],
            },
            {
                "name": "calculate_cost",
                "stage": 7,
                "description": "Calculate FINAL COST and supplementary values",
                "formulas": {
                    "K27": "J23 × K26 (FINAL COST)",
                    "C28": "(A28 × B28%) + A28 (Net Rate with GST)",
                    "B26": "A24/C24 × B24 (Work Ratio)",
                    "O9": "(O8 × M8) / 39.37",
                },
                "outputs": ["cost", "net_rate", "work_ratio", "total_card_calc"],
            },
        ],
    }


@app.get("/defaults", tags=["Calculator"])
async def get_defaults():
    """Get default values for all inputs (from Excel spreadsheet)."""
    return {
        "global_params": GlobalParams().model_dump(),
        "materials": [
            {"material_name": "Warp", "beam_tar": 110.0, "denier": 110.0, "rate": 325.0, "has_e_multiplier": False},
            {"material_name": "150 Lichi", "beam_tar": 140.0, "denier": 70.0, "rate": 252.0, "has_e_multiplier": True},
            {"material_name": "Shampen", "beam_tar": 280.0, "denier": 52.0, "rate": 300.0, "has_e_multiplier": True},
            {"material_name": "Weft-3", "beam_tar": 155.0, "denier": 0.0, "rate": 175.0, "has_e_multiplier": True},
            {"material_name": "Weft-4", "beam_tar": 155.0, "denier": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Weft-5", "beam_tar": 155.0, "denier": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Weft-6", "beam_tar": 155.0, "denier": 0.0, "rate": 0.0, "has_e_multiplier": True},
        ],
    }


@app.post("/calculate", response_model=CalculationResponse, tags=["Calculator"])
async def calculate_full(request: CalculationRequest):
    """
    🧮 **Full Calculation** — Run the complete LangGraph costing pipeline.

    Send 1-7 materials with their beam_tar, denier, and rate.
    Global parameters (saree_cut, job_rate, etc.) have defaults from the Excel file.

    **Pipeline:** START → Ans → Amt → Yarn Weight → Yarn Price → Aggregation → Job → Cost → END
    """
    try:
        state = build_initial_state(request.materials, request.global_params)

        start_time = time.perf_counter()
        result = costing_graph.invoke(state)
        exec_time = time.perf_counter() - start_time

        return format_response(result, exec_time)

    except ZeroDivisionError as e:
        raise HTTPException(status_code=400, detail=f"Division by zero in calculation: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@app.post("/calculate/quick", response_model=CalculationResponse, tags=["Calculator"])
async def calculate_quick(request: QuickCalcRequest):
    """
    ⚡ **Quick Calculation** — Flat input format for all 7 materials.

    All fields have defaults from the Excel spreadsheet.
    Just override the values you want to change.

    Example: Change only Warp denier → `{"warp_denier": 120}`
    """
    try:
        materials = [
            MaterialInput(material_name="Warp", beam_tar=request.warp_beam_tar, denier=request.warp_denier, rate=request.warp_rate, has_e_multiplier=False),
            MaterialInput(material_name="150 Lichi", beam_tar=request.lichi_beam_tar, denier=request.lichi_denier, rate=request.lichi_rate, has_e_multiplier=True),
            MaterialInput(material_name="Shampen", beam_tar=request.shampen_beam_tar, denier=request.shampen_denier, rate=request.shampen_rate, has_e_multiplier=True),
            MaterialInput(material_name="Weft-3", beam_tar=request.weft3_beam_tar, denier=request.weft3_denier, rate=request.weft3_rate, has_e_multiplier=True),
            MaterialInput(material_name="Weft-4", beam_tar=request.weft4_beam_tar, denier=request.weft4_denier, rate=request.weft4_rate, has_e_multiplier=True),
            MaterialInput(material_name="Weft-5", beam_tar=request.weft5_beam_tar, denier=request.weft5_denier, rate=request.weft5_rate, has_e_multiplier=True),
            MaterialInput(material_name="Weft-6", beam_tar=request.weft6_beam_tar, denier=request.weft6_denier, rate=request.weft6_rate, has_e_multiplier=True),
        ]

        params = GlobalParams(
            saree_cut=request.saree_cut,
            job_rate_k24=request.job_rate_k24,
            job_rate_m8=request.job_rate_m8,
            saree_cut_m7=request.saree_cut_m7,
        )

        state = build_initial_state(materials, params)

        start_time = time.perf_counter()
        result = costing_graph.invoke(state)
        exec_time = time.perf_counter() - start_time

        return format_response(result, exec_time)

    except ZeroDivisionError as e:
        raise HTTPException(status_code=400, detail=f"Division by zero in calculation: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


# ──────────────────────── Run Server ────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Textile Costing Calculator API")
    print("  Starting server on http://127.0.0.1:8000")
    print("  Swagger docs: http://127.0.0.1:8000/docs")
    print("=" * 50)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
