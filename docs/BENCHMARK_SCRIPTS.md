# Benchmark Execution Scripts

Helper shell code falls into **two families**:

| Family | Location | CLI | When to use |
|--------|----------|-----|-------------|
| **Multi-turn** | [`scripts/`](../scripts/) | `benchmark run-task` | Paper-aligned sweeps across `tasks/multi_turn/`, multiple models & agent patterns ([arXiv:2604.09678](https://arxiv.org/abs/2604.09678)). |
| **Single-turn / legacy** | Repository root (`run_quick_benchmark.sh`, `run_full_benchmark.sh`) | `benchmark run-llm` property batches | Faster checks of the older catalogued task families. |

Every `scripts/*.sh` file `cd`s to the benchmark root automatically (relative to the script path). Common environment variables: **`DAGENT_ENDPOINT`**, **`OLLAMA_HOST`**, **`RERUN_PLAN_FILE`** (for reruns), **`DAGENT_DIR`** / **`STUDY_SCRIPT`** (for `start_study_background.sh`). By default **`DAGENT_DIR`** resolves to **`agent_harness/`** inside this repo; override to point at a full **dagent** checkout if needed (for example workflows that rely on `--structure adaptive`, which this harness omits).

### `scripts/` inventory

| Script | Role |
|--------|------|
| `run_comparative_multiturn_study.sh` | Full factorial over default multi-turn tasks × agent patterns × listed models. Writes `results/comparative_study/<session>/`. |
| `run_single_model_comparison.sh` | Narrowed comparative matrix (tweak in-file arrays for ablations). |
| `run_multiturn_study.sh` | Multi-task sweep with GPT + Gemini defaults. |
| `run_ollama_multiturn_study.sh` | Multi-turn study targeting Ollama-hosted weights. |
| `run_adaptive_validation.sh` | Focused adaptive-structure validation ladder. Requires an agent checkout that still exposes **`structure=adaptive`** — not supported by **[`agent_harness/`](../agent_harness/)**. |
| `dry_run_study.sh` | Low turn/time limits for plumbing tests. |
| `run_bugfix_validation.sh` | Targeted regression checklist (edit `TASKS`/`AGENT_CONFIGS` as needed). |
| `rerun_failed_study_runs.sh` | Replays JSON plans (`scripts/rerun_plan.json`, see `rerun_plan.example.json`). |
| `start_study_background.sh` | Launches **`agent_harness`** (if nothing listens on port 8000) + comparative study via `nohup`/`setsid`. Override **`DAGENT_DIR`** for another agent checkout. |
| `run_baseline_study.sh` | Legacy property-level sweeps into `results/sessions/`. |
| `run_ollama_study.sh` | Legacy Ollama-facing property sweeps. |

## Available Scripts (repo root)

### 1. `run_quick_benchmark.sh` - Quick Test
**Purpose**: Fast validation and testing  
**Duration**: 1-2 hours  
**Task Count**: 60 tasks (10 per property × 3 properties × 2 models)

```bash
./run_quick_benchmark.sh [batch-name]
```

**Use Cases**:
- Testing infrastructure changes
- Validating new task definitions
- Quick comparison between models
- Pilot studies before full runs

**Example**:
```bash
# With default batch name (auto-generated timestamp)
./run_quick_benchmark.sh

# With custom batch name
./run_quick_benchmark.sh pilot_test_v1
```

---

### 2. `run_full_benchmark.sh` - Full Comparison
**Purpose**: Publication-quality statistical analysis  
**Duration**: 20-30 hours  
**Task Count**: 600 tasks (100 per property × 3 properties × 2 models)

```bash
./run_full_benchmark.sh [batch-name]
```

**Use Cases**:
- Research publications
- Comprehensive model comparisons
- Statistically rigorous evaluations
- Production benchmarks

**Example**:
```bash
# With default batch name (auto-generated timestamp)
./run_full_benchmark.sh

# With custom batch name for tracking
./run_full_benchmark.sh production_run_20251120
```

**Confirmation Prompt**: The full benchmark will ask for confirmation before starting due to the long runtime.

---

## What the Scripts Do

### Phase 1: Run Benchmarks
For each combination of property type and model:
1. Execute benchmark tasks
2. Store individual run results
3. Log progress and errors

Property types:
- `reachability`
- `bgp_configuration`
- `ospf_configuration`

Models:
- GPT-5-mini (OpenAI)
- Gemini 2.5 Pro (Google)

### Phase 2: Statistical Analysis
After all benchmarks complete:
1. **Comparison Analysis**: GPT-5-mini vs Gemini 2.5 Pro
   - T-test for significance
   - Effect size (Cohen's d)
   - Confidence intervals

2. **Property Analysis**: Performance by property type
   - Cross-model comparisons per property
   - Task difficulty rankings

3. **Testee Analysis**: Individual model performance
   - Per-property breakdowns
   - Overall metrics
   - Execution statistics

---

## Output Organization

### Results Structure
```
results/
  runs/                          # Individual benchmark runs
    run_<timestamp>_<id>.json
    ...
  property_results/              # Aggregated property results
    reachability_<timestamp>.json
    bgp_configuration_<timestamp>.json
    ospf_configuration_<timestamp>.json
  analysis/                      # Statistical analyses
    <batch-name>/                # Batch-specific folder
      comparison_*.json
      comparison_*_summary.csv
      property_*.json
      property_*_summary.csv
      testee_*.json
      testee_*_summary.csv

logs/                            # Execution logs
  benchmark_<batch-name>.log
```

### Batch Organization
Each benchmark run creates a dedicated folder in `results/analysis/` containing:
- **JSON files**: Complete analysis data (for archiving/reproducibility)
- **CSV files**: Summary tables (for Excel/R/Python/plotting)

---

## Error Handling

Both scripts are designed to be resilient:
- **Continue on error**: If a single task fails, the script continues with remaining tasks
- **Logging**: All output is logged to `logs/benchmark_<batch-name>.log`
- **Exit codes**: Non-zero exit codes are logged but don't stop execution

This ensures maximum data collection even if some tasks encounter issues.

---

## Configuration

You can modify the scripts to adjust:
- **Task limit**: Change `TASK_LIMIT` variable
- **Property types**: Modify `PROPERTY_TYPES` array
- **Models**: Modify `MODELS` array
- **Delays**: Adjust `sleep` commands for API rate limiting

Example modification:
```bash
# In run_full_benchmark.sh
TASK_LIMIT=50  # Instead of 100
```

---

## Monitoring Progress

### Real-time Monitoring
```bash
# Watch the log file in real-time
tail -f logs/benchmark_<batch-name>.log

# Check how many runs have completed
ls -1 results/runs/*.json | wc -l

# Check property results
ls -lh results/property_results/
```

### Progress Indicators
The scripts display:
- Current task number / total tasks
- Property type being tested
- Model being evaluated
- Estimated time remaining

---

## Post-Benchmark Analysis

After the script completes, you can:

### 1. View Analysis Results
```bash
# List all analysis files for your batch
ls -lh results/analysis/<batch-name>/

# View CSV summaries (human-readable)
cat results/analysis/<batch-name>/*_summary.csv
```

### 2. Compare with Previous Runs
```bash
# List all batch folders
ls -d results/analysis/*/

# Compare two batches
diff results/analysis/batch1/comparison_*_summary.csv \
     results/analysis/batch2/comparison_*_summary.csv
```

### 3. Re-run Analysis
If you want to re-analyze with different settings:
```bash
BATCH_NAME="reanalysis_$(date +%Y%m%d)"

benchmark analyze llm_openai_gpt-5-mini,llm_gemini_gemini-2.5-pro \
  --batch-name "$BATCH_NAME"
```

---

## Best Practices

### 1. Use Descriptive Batch Names
```bash
# Good: Descriptive and dated
./run_full_benchmark.sh gpt5_mini_vs_gemini_25pro_20251120

# Bad: Generic
./run_full_benchmark.sh test
```

### 2. Monitor Long Runs
```bash
# Run in tmux/screen for long runs
tmux new -s benchmark
./run_full_benchmark.sh production_v1
# Detach with Ctrl+B, D
# Reattach later: tmux attach -t benchmark
```

### 3. Archive Results
```bash
# After completion, archive the batch
tar -czf benchmark_run_20251120.tar.gz \
  results/analysis/benchmark_run_20251120/ \
  logs/benchmark_benchmark_run_20251120.log
```

### 4. Check Disk Space
600 tasks with logs can use significant disk space (~5-10 GB):
```bash
df -h .
du -sh results/
```

---

## Troubleshooting

### Script Won't Start
```bash
# Make sure scripts are executable
chmod +x run_full_benchmark.sh run_quick_benchmark.sh

# Check you're in the project directory
pwd  # Should show: /path/to/benchmark
```

### API Errors
If you see API timeout or rate limit errors:
- Check API keys are set (OPENAI_API_KEY, GOOGLE_API_KEY)
- Increase sleep delays in the script
- Reduce TASK_LIMIT

### Out of Memory
If containerlab runs fail due to memory:
- Reduce TASK_LIMIT
- Run benchmarks for one property type at a time
- Close other applications

### Partial Results
If the script is interrupted:
- Completed runs are saved
- Re-run the script with the same batch name
- The analysis will use all available data

---

## Example Workflow

### Research Publication Workflow
```bash
# 1. Quick test to validate setup
./run_quick_benchmark.sh validation_test
# Review results in results/analysis/validation_test/

# 2. Run full benchmark
./run_full_benchmark.sh paper_experiment_20251120
# Wait 20-30 hours

# 3. Archive results
tar -czf paper_experiment_20251120.tar.gz \
  results/analysis/paper_experiment_20251120/ \
  logs/benchmark_paper_experiment_20251120.log

# 4. Extract key findings
cat results/analysis/paper_experiment_20251120/comparison_*_summary.csv
```

---

## Statistical Power

### Quick Test (10 tasks)
- Can detect **large effects** (d ≥ 0.8)
- Suitable for: pilot studies, validation, debugging
- **Not recommended** for publication

### Full Test (100 tasks)
- Can detect **medium effects** (d ≥ 0.5) with 80% power
- Suitable for: research papers, production comparisons
- **Recommended** for statistically rigorous evaluation

See `docs/TASK_SCALING_SUMMARY.md` for detailed statistical power analysis.

---

## Questions?

For more information:
- Task generation: `docs/TASK_SCALING_SUMMARY.md`
- Analysis interpretation: `docs/ANALYSIS_GUIDE.md`
- CLI usage: `docs/CLI_USAGE.md`

