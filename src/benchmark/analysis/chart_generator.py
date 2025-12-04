import json
import matplotlib.pyplot as plt
import numpy as np
import os
import argparse
from typing import Dict, Any

def load_analysis_results(filepath: str) -> Dict[str, Any]:
    """Load analysis results from a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def create_overall_comparison_chart(data: Dict[str, Any], output_dir: str):
    """Create a bar chart comparing overall scores of testees."""
    print("Creating overall comparison chart...")
    
    score_comparison = data.get("score_comparison", {}).get("testee_scores", {})
    if not score_comparison:
        print("No score comparison data found.")
        return

    testees = list(score_comparison.keys())
    metrics = ["completeness", "robustness", "syntactic_validity", "final_score"]
    
    x = np.arange(len(metrics))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for i, testee in enumerate(testees):
        scores = [score_comparison[testee].get(m, 0) for m in metrics]
        offset = width * i
        rects = ax.bar(x + offset, scores, width, label=testee)
        
        # Add value labels
        ax.bar_label(rects, padding=3, fmt='%.2f')

    ax.set_ylabel('Score')
    ax.set_title('Overall Performance Comparison')
    ax.set_xticks(x + width / 2 * (len(testees) - 1))
    ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics])
    ax.legend()
    ax.set_ylim(0, 1.1)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'overall_comparison.png'))
    plt.close()

def create_property_breakdown_chart(data: Dict[str, Any], output_dir: str):
    """Create charts for property-specific performance."""
    print("Creating property breakdown charts...")
    
    property_breakdown = data.get("property_breakdown", {})
    if not property_breakdown:
        print("No property breakdown data found.")
        return

    metrics = ["completeness", "robustness", "syntactic_validity", "final_score"]
    
    for metric in metrics:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        prop_types = list(property_breakdown.keys())
        testees = list(property_breakdown[prop_types[0]]["testee_stats"].keys())
        
        x = np.arange(len(prop_types))
        width = 0.35
        
        for i, testee in enumerate(testees):
            values = []
            for prop in prop_types:
                stats = property_breakdown[prop]["testee_stats"].get(testee, {}).get("aggregate_scores", {})
                values.append(stats.get(metric, 0))
            
            offset = width * i
            rects = ax.bar(x + offset, values, width, label=testee)
            ax.bar_label(rects, padding=3, fmt='%.2f')
            
        ax.set_ylabel('Score')
        ax.set_title(f'{metric.replace("_", " ").title()} by Property Type')
        ax.set_xticks(x + width / 2 * (len(testees) - 1))
        ax.set_xticklabels([p.replace('_', ' ').title() for p in prop_types], rotation=15, ha='right')
        ax.legend()
        ax.set_ylim(0, 1.1)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'property_breakdown_{metric}.png'))
        plt.close()

def main():
    parser = argparse.ArgumentParser(description="Generate charts from benchmark analysis results.")
    parser.add_argument("analysis_file", help="Path to the analysis results JSON file")
    parser.add_argument("--output-dir", default="results/charts", help="Directory to save charts")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.analysis_file):
        print(f"Error: File {args.analysis_file} not found.")
        return
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    data = load_analysis_results(args.analysis_file)
    
    # Handle potentially nested comparison analysis structure
    if "comparison_analysis" in data:
        data = data["comparison_analysis"]
        
    create_overall_comparison_chart(data, args.output_dir)
    create_property_breakdown_chart(data, args.output_dir)
    
    print(f"Charts generated in {args.output_dir}")

if __name__ == "__main__":
    main()

