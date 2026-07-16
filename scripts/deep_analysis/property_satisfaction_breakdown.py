import json
from pathlib import Path
import collections
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from deep_analysis.run_loader import load_and_enrich

def main():
    data_dir = Path(__file__).parent.parent.parent / "results" / "comparatives_all"
    runs = load_and_enrich(data_dir)
    
    tasks = ["troubleshoot_bgp_route_filtering", "ccie_bgp_dual_homing_expert", "ccnp_multiarea_ospf_intermediate"]
    
    res = collections.defaultdict(lambda: collections.defaultdict(lambda: {"total": 0, "sat": 0}))
    
    for d in runs:
        task = d["task_id"]
        if task not in tasks:
            continue
        
        prop_results = d.get("property_results", [])
        for pr in prop_results:
            pid = pr["property_id"]
            sat = pr.get("satisfied", False)
            res[task][pid]["total"] += 1
            if sat:
                res[task][pid]["sat"] += 1
                
    for task, props in res.items():
        print(f"\nTask: {task}")
        for pid, counts in sorted(props.items(), key=lambda x: x[1]["sat"]/x[1]["total"] if x[1]["total"]>0 else 0, reverse=True):
            pct = counts["sat"]/counts["total"]*100 if counts["total"]>0 else 0
            print(f"  {pid:35s}: {pct:5.1f}% ({counts['sat']}/{counts['total']})")

if __name__ == "__main__":
    main()
