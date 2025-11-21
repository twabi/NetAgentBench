# Task Scaling Summary

## Overview

Scaled the benchmark task suite from 121 tasks to 329 tasks to achieve statistical significance in comparative analyses (target: 100+ tasks per property type).

## Task Counts

### Before Scaling
- Reachability: 61 tasks
- BGP Configuration: 28 tasks
- OSPF Configuration: 32 tasks
- **Total: 121 tasks**

### After Scaling
- Reachability: 127 tasks ✅
- BGP Configuration: 102 tasks ✅
- OSPF Configuration: 100 tasks ✅
- **Total: 329 tasks**

## Statistical Significance

### Sample Size Requirements
For independent two-sample t-tests with:
- Power: 80%
- Alpha: 0.05 (two-tailed)
- Effect size (d): 0.5 (medium effect)

**Required: ~64 tasks per group (128 total)**

Our scaling ensures we can detect medium-sized performance differences with adequate statistical power.

### Current Capability
- **100+ tasks per property type** enables detection of medium effects (d ≥ 0.5)
- Provides robust statistical power for research-quality comparisons
- Allows for property-specific subgroup analyses

## Task Diversity Enhancements

### Topology Variations
Each property type now includes diverse topologies:

#### Reachability (127 tasks)
- **Linear**: 18 node counts (2 to 20 nodes)
  - First-to-last, middle-to-end, reverse direction tests
- **Star**: 16 node counts (3 to 20 nodes)
  - Hub-to-spoke, spoke-to-spoke tests
- **Ring**: 14 node counts (3 to 20 nodes)
  - Full-ring, halfway tests
- **Mesh**: 5 node counts (3 to 7 nodes)
  - Various node pair combinations
- **Tree**: Hierarchical structures with varying depth and branching
  - Depth: 2-3, Branching: 2-4

#### BGP Configuration (102 tasks)
- **eBGP Linear**: 17 configurations (2 to 30 AS)
- **iBGP Route Reflector**: 16 configurations (3 to 30 routers)
- **eBGP Mesh**: 5 configurations (3 to 7 AS)
- **iBGP Mesh**: 6 configurations (3 to 8 routers)
- **eBGP Ring**: 14 configurations (3 to 24 AS)
- **iBGP Ring**: 8 configurations (3 to 12 routers)
- **Tree Topologies**: eBGP, iBGP, and mixed scenarios
  - Depth: 2-3, Branching: 2-5
- **Mixed eBGP/iBGP**: 6 configurations

#### OSPF Configuration (100 tasks)
- **Single Area (Area 0)**:
  - Linear: 17 configurations (2 to 25 nodes)
  - Star: 16 configurations (3 to 25 nodes)
  - Ring: 14 configurations (3 to 25 nodes)
  - Mesh: 5 configurations (3 to 7 nodes)
  - Tree: 8 configurations (various depth/branching)
- **Multi-Area**:
  - Tree: 20 configurations with ABR scenarios
  - Linear: 12 configurations (4 to 25 nodes)
  - Ring: 7 configurations (6 to 24 nodes)

### Key Features
- **No duplicate topologies**: Each task is unique
- **Scalability testing**: Node counts from 2 to 30
- **Protocol variations**: eBGP, iBGP, single-area, multi-area
- **Test scenario diversity**: Different source/destination pairs
- **Complexity gradient**: From simple 2-node to complex 30-node scenarios

## Generator Modifications

### Files Modified
1. `benchmark-tasks/generators/generate_reachability_tasks.py`
   - Expanded node count ranges
   - Added tree topologies
   - Added bidirectional and halfway tests

2. `benchmark-tasks/generators/generate_bgp_tasks.py`
   - Expanded all topology types
   - Added iBGP ring scenarios
   - Added tree variations (eBGP, iBGP, mixed)
   - Increased scale to 30-node topologies

3. `benchmark-tasks/generators/generate_ospf_tasks.py`
   - Expanded single-area scenarios
   - Added single-area tree topologies
   - Expanded multi-area scenarios significantly
   - Added multi-area linear and ring configurations

### Task Generation Process
```bash
cd benchmark-tasks/generators
poetry run python generate_all_tasks.py
```

Output:
- 316 new task definitions generated
- All tasks validated against Pydantic models
- Task index updated: `benchmark-tasks/index.json`
- Individual JSON files per task in property-specific directories

## Verification

### Task Loading
```python
from benchmark.task_repository import TaskRepository
repo = TaskRepository()
tasks = repo.load_all_tasks()
# Total: 329 tasks loaded
```

### Uniqueness Check
- ✅ All task IDs are unique
- ✅ No duplicate topologies
- ✅ All tasks validated successfully

## Research Impact

### Statistical Power
With 100+ tasks per property type, we can now:
- Detect medium effect sizes (d ≥ 0.5) with 80% power
- Perform robust property-specific comparisons
- Conduct subgroup analyses (e.g., by topology type)
- Achieve publication-quality statistical rigor

### Comparison Analysis Example
For GPT-5-mini vs Gemini 2.5 Pro with 100 tasks each:
- Current small difference (d = 0.075) would require ~2,800 tasks
- Medium differences (d = 0.5) are now detectable with adequate power
- Large differences (d ≥ 0.8) are highly detectable

### Future Extensions
The task suite can be further expanded by:
- Adding more property types (e.g., VLAN, ACL, QoS)
- Creating hybrid topologies (combining multiple protocols)
- Adding failure scenario tasks
- Implementing dynamic topology changes

## Automated Benchmark Scripts

### Quick Test (10 tasks per property, ~1-2 hours)
```bash
# Run quick benchmark test with automatic analysis
./run_quick_benchmark.sh [optional-batch-name]

# Example with custom batch name
./run_quick_benchmark.sh pilot_study_v1
```

This runs:
- 10 tasks × 3 property types × 2 models = 60 total tasks
- Full statistical analysis with batch organization
- Results saved to: `results/analysis/<batch_name>/`

### Full Benchmark (100 tasks per property, ~20-30 hours)
```bash
# Run full benchmark comparison with automatic analysis
./run_full_benchmark.sh [optional-batch-name]

# Example with custom batch name
./run_full_benchmark.sh production_run_20251120
```

This runs:
- 100 tasks × 3 property types × 2 models = 600 total tasks
- Comprehensive statistical analysis
- Results saved to: `results/analysis/<batch_name>/`
- Log saved to: `logs/benchmark_<batch_name>.log`

### Manual Commands

#### Single Property Type (100 tasks)
```bash
# Reachability with GPT-5-mini
benchmark run-llm reachability --provider openai --model gpt-5-mini --limit 100

# BGP with Gemini 2.5 Pro
benchmark run-llm bgp_configuration --provider gemini --model gemini-2.5-pro --limit 100

# OSPF with GPT-5-mini
benchmark run-llm ospf_configuration --provider openai --model gpt-5-mini --limit 100
```

#### Full Comparison Study with Batch Organization
```bash
# Set batch name
BATCH_NAME="my_benchmark_$(date +%Y%m%d)"

# Run all tasks for both models
for property in reachability bgp_configuration ospf_configuration; do
  benchmark run-llm $property --provider openai --model gpt-5-mini --limit 100
  benchmark run-llm $property --provider gemini --model gemini-2.5-pro --limit 100
done

# Analyze results (all organized in one batch folder)
benchmark analyze llm_openai_gpt-5-mini,llm_gemini_gemini-2.5-pro --batch-name "$BATCH_NAME"
benchmark analyze reachability --batch-name "$BATCH_NAME"
benchmark analyze bgp_configuration --batch-name "$BATCH_NAME"
benchmark analyze ospf_configuration --batch-name "$BATCH_NAME"
benchmark analyze llm_openai_gpt-5-mini --batch-name "$BATCH_NAME"
benchmark analyze llm_gemini_gemini-2.5-pro --batch-name "$BATCH_NAME"
```

### Batch Organization

Analysis results are now organized by batch:

```
results/
  analysis/
    benchmark_run_20251120_143052/    # Batch folder
      comparison_llm_openai_gpt-5-mini_llm_gemini_gemini-2.5-pro_20251120_143102.json
      comparison_llm_openai_gpt-5-mini_llm_gemini_gemini-2.5-pro_20251120_143102_summary.csv
      property_reachability_20251120_143105.json
      property_reachability_20251120_143105_summary.csv
      property_bgp_configuration_20251120_143108.json
      property_bgp_configuration_20251120_143108_summary.csv
      ...
    quick_test_20251120_150000/        # Another batch
      ...
```

Benefits:
- ✅ Each benchmark run is isolated in its own folder
- ✅ Easy to compare results across different runs
- ✅ No file crowding in the analysis directory
- ✅ Clear organization for publication and archiving

## Conclusion

The task suite has been successfully scaled to support statistically rigorous comparative research. The 329-task benchmark provides:
- Adequate statistical power for medium effect detection
- Diverse topology coverage across property types
- Non-repetitive, unique test scenarios
- Research-quality experimental design

This scaling ensures that observed performance differences are statistically meaningful and not artifacts of small sample sizes.

