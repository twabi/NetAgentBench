import logging
import sys
from pathlib import Path

# Add src to python path if running as script
sys.path.append(str(Path(__file__).parent.parent.parent))

from benchmark.storage import ResultsStorage
from benchmark.scoring.metrics import ScoringCalculator
from benchmark.models.results import BenchmarkResult

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def recalculate_scores():
    """
    Recalculate scores for all existing benchmark runs.
    
    This is useful when scoring logic or weights change (e.g., disabling efficiency score).
    It updates the JSON files in place.
    """
    storage = ResultsStorage()
    calculator = ScoringCalculator()
    
    # Verify weights
    logger.info(f"Using weights: {calculator.DEFAULT_WEIGHTS}")
    
    # Get all run IDs
    run_ids = storage.list_runs()
    logger.info(f"Found {len(run_ids)} runs to update.")
    
    updated_count = 0
    error_count = 0
    
    for run_id in run_ids:
        try:
            # Load result
            result = storage.load_result(run_id)
            
            # Use existing component scores because structured execution logs 
            # might not be preserved in BenchmarkResult (only strings), preventing
            # re-calculation of syntactic validity.
            
            old_scoring = result.scoring
            weights = calculator.DEFAULT_WEIGHTS
            
            # Re-calculate Final Score
            # We use the existing efficiency score value, but the new weight (0.0) 
            # will ensure it doesn't affect the final score.
            
            final_score = calculator.compute_final_score(
                completeness=old_scoring.completeness,
                robustness=old_scoring.robustness,
                syntactic_validity=old_scoring.syntactic_validity,
                efficiency=old_scoring.efficiency,
                weights=weights
            )
            
            # Create new ScoringResult with updated final score and weights
            # We model_copy to preserve other fields, then update
            new_scoring = old_scoring.model_copy(update={
                "final_score": final_score,
                "weights": weights
            })
            
            result.scoring = new_scoring
            
            # Save updated result
            storage.save_result(result)
            updated_count += 1
            
            if updated_count % 50 == 0:
                logger.info(f"Updated {updated_count} runs...")
                
        except Exception as e:
            logger.error(f"Failed to update run {run_id}: {e}")
            error_count += 1

    logger.info(f"Finished. Updated: {updated_count}, Errors: {error_count}")

if __name__ == "__main__":
    recalculate_scores()
