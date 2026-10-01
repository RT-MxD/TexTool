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
  GET  /threads            - List saved calculation threads
  GET  /threads/{id}       - Get a specific thread with inputs & results
  DELETE /threads/{id}     - Delete a thread
  DELETE /threads          - Delete all threads

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

from db import save_thread, list_threads, get_thread, delete_thread, delete_all_threads

# ──────────────────────── Pydantic Models ────────────────────────

class MaterialInput(BaseModel):
    """Input for a single material."""
    material_name: str = Field(..., description="Name of the material (e.g., 'Warp', 'Material-2')")
    denier: float = Field(..., description="Denier value (Column B)")
    peak: float = Field(..., description="Peak value (Column C)")
    panno: float = Field(..., description="Panno value (Column D)")
    rate: float = Field(..., description="Rate per unit (Column H)")
    has_e_multiplier: bool = Field(
        True,
        description="False for Warp (3-param: B*C*D/divisor), True for others (4-param: B*C*D*E/divisor)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "material_name": "Material-2",
                "denier":0.0,
                "peak": 0.0,
                "panno": 0.0,
                "rate": 0.0,
                "has_e_multiplier": True,
            }
        }


class GlobalParams(BaseModel):
    """Global parameters for the calculation."""
    saree_cut: float = Field(0.0, description="Saree Cut (K26)")
    job_rate_k24: float = Field(0.0, description="Job Rate (K24)")
    job_rate_m8: float = Field(0.0, description="Job Rate (M8)")
    saree_cut_m7: float = Field(0.0, description="Saree Cut for job calc (M7)")
    total_card: float = Field(0.0, description="Total Card (O8)")
    divisor: float = Field(0.0, description="Divisor for Ans calculation")


class CalculationRequest(BaseModel):
    """Full calculation request with materials and global params."""
    design_no: str = Field("", description="Optional design number (saved as title)")
    materials: List[MaterialInput] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of materials (1-10). First is Warp (fixed), rest are user-named"
    )
    global_params: GlobalParams = Field(
        default_factory=GlobalParams,
        description="Global calculation parameters (all have defaults)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "materials": [
                    {"material_name": "Warp", "denier": 110.0, "peak": 110.0, "panno": 110.0, "rate": 325.0, "has_e_multiplier": False},
                    {"material_name": "Material-2", "denier": 140.0, "peak": 70.0, "panno": 70.0, "rate": 252.0, "has_e_multiplier": True},
                    {"material_name": "Material-3", "denier": 280.0, "peak": 52.0, "panno": 52.0, "rate": 300.0, "has_e_multiplier": True},
                ],
                "global_params": {
                    "saree_cut": 6.6,
                    "job_rate_k24": 0.25,
                    "job_rate_m8": 0.28,
                    "saree_cut_m7": 6.2,
                    "divisor": 9000000.0,
                }
            }
        }


class QuickCalcRequest(BaseModel):
    """Simplified request — denier, peak, panno, rate for 10 materials."""
    warp_beam_tar: float = Field(110.0, description="Warp Denier (B)")
    warp_peak: float = Field(110.0, description="Warp Peak (C)")
    warp_denier: float = Field(110.0, description="Warp Panno (D)")
    warp_rate: float = Field(325.0, description="Warp Rate (H)")

    mat2_name: str = Field("Material-2", description="Material 2 Name")
    mat2_beam_tar: float = Field(140.0, description="Material 2 Denier")
    mat2_peak: float = Field(70.0, description="Material 2 Peak")
    mat2_denier: float = Field(70.0, description="Material 2 Panno")
    mat2_rate: float = Field(252.0, description="Material 2 Rate")

    mat3_name: str = Field("Material-3", description="Material 3 Name")
    mat3_beam_tar: float = Field(280.0, description="Material 3 Denier")
    mat3_peak: float = Field(52.0, description="Material 3 Peak")
    mat3_denier: float = Field(52.0, description="Material 3 Panno")
    mat3_rate: float = Field(300.0, description="Material 3 Rate")

    mat4_name: str = Field("Material-4", description="Material 4 Name")
    mat4_beam_tar: float = Field(155.0, description="Material 4 Denier")
    mat4_peak: float = Field(0.0, description="Material 4 Peak")
    mat4_denier: float = Field(0.0, description="Material 4 Panno")
    mat4_rate: float = Field(175.0, description="Material 4 Rate")

    mat5_name: str = Field("Material-5", description="Material 5 Name")
    mat5_beam_tar: float = Field(155.0, description="Material 5 Denier")
    mat5_peak: float = Field(0.0, description="Material 5 Peak")
    mat5_denier: float = Field(0.0, description="Material 5 Panno")
    mat5_rate: float = Field(0.0, description="Material 5 Rate")

    mat6_name: str = Field("Material-6", description="Material 6 Name")
    mat6_beam_tar: float = Field(155.0, description="Material 6 Denier")
    mat6_peak: float = Field(0.0, description="Material 6 Peak")
    mat6_denier: float = Field(0.0, description="Material 6 Panno")
    mat6_rate: float = Field(0.0, description="Material 6 Rate")

    mat7_name: str = Field("Material-7", description="Material 7 Name")
    mat7_beam_tar: float = Field(155.0, description="Material 7 Denier")
    mat7_peak: float = Field(0.0, description="Material 7 Peak")
    mat7_denier: float = Field(0.0, description="Material 7 Panno")
    mat7_rate: float = Field(0.0, description="Material 7 Rate")

    mat8_name: str = Field("Material-8", description="Material 8 Name")
    mat8_beam_tar: float = Field(0.0, description="Material 8 Denier")
    mat8_peak: float = Field(0.0, description="Material 8 Peak")
    mat8_denier: float = Field(0.0, description="Material 8 Panno")
    mat8_rate: float = Field(0.0, description="Material 8 Rate")

    mat9_name: str = Field("Material-9", description="Material 9 Name")
    mat9_beam_tar: float = Field(0.0, description="Material 9 Denier")
    mat9_peak: float = Field(0.0, description="Material 9 Peak")
    mat9_denier: float = Field(0.0, description="Material 9 Panno")
    mat9_rate: float = Field(0.0, description="Material 9 Rate")

    mat10_name: str = Field("Material-10", description="Material 10 Name")
    mat10_beam_tar: float = Field(0.0, description="Material 10 Denier")
    mat10_peak: float = Field(0.0, description="Material 10 Peak")
    mat10_denier: float = Field(0.0, description="Material 10 Panno")
    mat10_rate: float = Field(0.0, description="Material 10 Rate")

    saree_cut: float = Field(6.6, description="Saree Cut (K26)")
    job_rate_k24: float = Field(0.25, description="Job Rate (K24)")
    job_rate_m8: float = Field(0.28, description="Job Rate (M8)")
    saree_cut_m7: float = Field(6.2, description="Saree Cut M7")
    divisor: float = Field(9000000.0, description="Divisor for Ans calculation")


class MaterialResult(BaseModel):
    """Calculated result for a single material."""
    material_name: str
    denier: float
    peak: float
    panno: float
    rate: float
    ans: float = Field(description="G column - Base calculation")
    amt: float = Field(description="G next row - Ans * Rate")
    yarn_weight: float = Field(description="I column - Ans/100 * Saree Cut")
    yarn_price: float = Field(description="J column - Rate * Yarn Weight")


class CalculationResponse(BaseModel):
    """Complete calculation response."""
    # Per-material results
    materials: List[MaterialResult]

    # Aggregation results
    total_pick: float = Field(description="H26 - Sum of peak values (excluding Warp)")
    sum_amt: float = Field(description="I21 - Sum of all Amt values")
    j21: float = Field(description="J21 = I21/100")
    j22: float = Field(description="J22 = H26 * K24 (Pick * Job Rate)")
    j23: float = Field(description="J23 = J21 + J22")

    # Final outputs
    total_job: float = Field(description="N9 - TOTAL JOB")
    total_job_alt: float = Field(description="L24 - TOTAL JOB (alternative)")
    total_amt_yarn: float = Field(description="M24 - TOTAL AMT YARN")
    n6: float = Field(description="N6 - Top 3 Rates (Warp + next 2)")
    total_yarn_job: float = Field(description="N11 - TOTAL YARN + JOB")
    cost: float = Field(description="K27 - FINAL COST = J23 * Saree Cut")

    # Metadata
    workflow_nodes_executed: List[str]
    execution_time_ms: float
    thread_id: Optional[str] = Field(None, description="Anonymous thread ID (auto-saved)")


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
- **Warp** (3-param formula: B×C×D / divisor)
- **Materials 2 through 10** (4-param: B×C×D×E / divisor)

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
            denier=m.denier,
            peak=m.peak,
            panno=m.panno,
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
        divisor=params.divisor,
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


def format_response(result: dict, exec_time: float) -> CalculationResponse:
    """Convert LangGraph final state to API response."""
    material_results = []
    for mat in result["materials"]:
        material_results.append(MaterialResult(
            material_name=mat["material_name"],
            denier=mat["denier"],
            peak=mat["peak"],
            panno=mat["panno"],
            rate=mat["rate"],
            ans=round(mat["ans"], 4),
            amt=round(mat["amt"], 4),
            yarn_weight=round(mat["yarn_weight"],2),
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
        n6=round(result["n6"], 4),
        total_yarn_job=round(result["total_yarn_job"], 4),
        cost=round(result["cost"], 4),
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
                "inputs": ["denier (B)", "panno (C)", "multiplier_d (D=50)", "multiplier_e (E=100)"],
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
                    "H26": "Sum of peak values (excluding Warp) (Total Pick)",
                    "I21": "Sum of all Amt values",
                    "J21": "I21 / 100",
                    "N6": "J3 + J6 + J9 (top 3 Rates)",
                    "M24": "Sum of all Rates (TOTAL AMT YARN)",
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
                "description": "Calculate FINAL COST",
                "formulas": {
                    "K27": "J23 × K26 (FINAL COST)",
                },
                "outputs": ["cost"],
            },
        ],
    }


@app.get("/defaults", tags=["Calculator"])
async def get_defaults():
    """Get default values for all inputs."""
    return {
        "global_params": GlobalParams().model_dump(),
        "materials": [
            {"material_name": "Warp", "denier": 110.0, "peak": 110.0, "panno": 110.0, "rate": 325.0, "has_e_multiplier": False},
            {"material_name": "Material-2", "denier": 140.0, "peak": 70.0, "panno": 70.0, "rate": 252.0, "has_e_multiplier": True},
            {"material_name": "Material-3", "denier": 280.0, "peak": 52.0, "panno": 52.0, "rate": 300.0, "has_e_multiplier": True},
            {"material_name": "Material-4", "denier": 155.0, "peak": 0.0, "panno": 0.0, "rate": 175.0, "has_e_multiplier": True},
            {"material_name": "Material-5", "denier": 155.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Material-6", "denier": 155.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Material-7", "denier": 155.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Material-8", "denier": 0.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Material-9", "denier": 0.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
            {"material_name": "Material-10", "denier": 0.0, "peak": 0.0, "panno": 0.0, "rate": 0.0, "has_e_multiplier": True},
        ],
    }


@app.post("/calculate", response_model=CalculationResponse, tags=["Calculator"])
async def calculate_full(request: CalculationRequest):
    """
    🧮 **Full Calculation** — Run the complete LangGraph costing pipeline.

    Send 1-10 materials with their denier, peak, panno, and rate.
    Global parameters (saree_cut, job_rate, etc.) have defaults from the Excel file.
    Every calculation is auto-saved as an anonymous thread.

    **Pipeline:** START → Ans → Amt → Yarn Weight → Yarn Price → Aggregation → Job → Cost → END
    """
    try:
        state = build_initial_state(request.materials, request.global_params)

        start_time = time.perf_counter()
        result = costing_graph.invoke(state)
        exec_time = time.perf_counter() - start_time

        response = format_response(result, exec_time)

        # Auto-save as anonymous thread
        try:
            materials_dicts = [m.model_dump() for m in request.materials]
            global_params_dict = request.global_params.model_dump()
            results_dict = response.model_dump()
            thread_id = save_thread(materials_dicts, global_params_dict, results_dict, title=request.design_no)
            response.thread_id = thread_id
        except Exception:
            pass  # Don't fail the calculation if saving fails

        return response

    except ZeroDivisionError as e:
        raise HTTPException(status_code=400, detail=f"Division by zero in calculation: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@app.post("/calculate/quick", response_model=CalculationResponse, tags=["Calculator"])
async def calculate_quick(request: QuickCalcRequest):
    """
    ⚡ **Quick Calculation** — Flat input format for all 10 materials.

    All fields have defaults. Just override the values you want to change.
    """
    try:
        materials = [
            MaterialInput(material_name="Warp", denier=request.warp_beam_tar, peak=request.warp_peak, panno=request.warp_denier, rate=request.warp_rate, has_e_multiplier=False),
            MaterialInput(material_name=request.mat2_name, denier=request.mat2_beam_tar, peak=request.mat2_peak, panno=request.mat2_denier, rate=request.mat2_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat3_name, denier=request.mat3_beam_tar, peak=request.mat3_peak, panno=request.mat3_denier, rate=request.mat3_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat4_name, denier=request.mat4_beam_tar, peak=request.mat4_peak, panno=request.mat4_denier, rate=request.mat4_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat5_name, denier=request.mat5_beam_tar, peak=request.mat5_peak, panno=request.mat5_denier, rate=request.mat5_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat6_name, denier=request.mat6_beam_tar, peak=request.mat6_peak, panno=request.mat6_denier, rate=request.mat6_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat7_name, denier=request.mat7_beam_tar, peak=request.mat7_peak, panno=request.mat7_denier, rate=request.mat7_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat8_name, denier=request.mat8_beam_tar, peak=request.mat8_peak, panno=request.mat8_denier, rate=request.mat8_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat9_name, denier=request.mat9_beam_tar, peak=request.mat9_peak, panno=request.mat9_denier, rate=request.mat9_rate, has_e_multiplier=True),
            MaterialInput(material_name=request.mat10_name, denier=request.mat10_beam_tar, peak=request.mat10_peak, panno=request.mat10_denier, rate=request.mat10_rate, has_e_multiplier=True),
        ]

        params = GlobalParams(
            saree_cut=request.saree_cut,
            job_rate_k24=request.job_rate_k24,
            job_rate_m8=request.job_rate_m8,
            saree_cut_m7=request.saree_cut_m7,
            divisor=request.divisor,
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


# ──────────────────────── Thread Endpoints ────────────────────────

@app.get("/threads", tags=["Threads"])
async def api_list_threads(limit: int = 50):
    """📋 List all saved calculation threads (newest first)."""
    threads = list_threads(limit=limit)
    return {"threads": threads, "count": len(threads)}


@app.get("/threads/{thread_id}", tags=["Threads"])
async def api_get_thread(thread_id: str):
    """🔍 Get a specific thread with its inputs and results."""
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    return thread


@app.delete("/threads/{thread_id}", tags=["Threads"])
async def api_delete_thread(thread_id: str):
    """🗑️ Delete a specific thread."""
    deleted = delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    return {"message": f"Thread '{thread_id}' deleted", "success": True}


@app.delete("/threads", tags=["Threads"])
async def api_delete_all_threads():
    """🗑️ Delete ALL saved threads."""
    count = delete_all_threads()
    return {"message": f"Deleted {count} thread(s)", "count": count}


# ──────────────────────── Run Server ────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Textile Costing Calculator API")
    print("  Starting server on http://127.0.0.1:8000")
    print("  Swagger docs: http://127.0.0.1:8000/docs")
    print("=" * 50)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
