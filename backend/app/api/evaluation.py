import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/evaluation", tags=["Evaluation & Benchmark Metrics"])

EVAL_RESULTS_PATH = Path(__file__).parent.parent.parent / "evaluation_results.json"

@router.get("/benchmark")
def get_benchmark_results():
    """
    Returns actual measured evaluation metrics, confusion matrix, and latencies
    generated from benchmark test fixtures.
    """
    if not EVAL_RESULTS_PATH.exists():
        return {
            "status": "NOT_EVALUATED",
            "message": "Benchmark has not yet been executed. Run 'python -m scripts.benchmark_eval' to generate real metrics."
        }
    
    try:
        with open(EVAL_RESULTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read benchmark results: {str(e)}")
