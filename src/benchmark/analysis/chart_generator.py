import json
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import os
import argparse
from typing import Dict, Any

# Set professional academic style
matplotlib.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 14,
    'axes.linewidth': 1.0,
    'grid.linewidth': 0.5,
    'lines.linewidth': 1.5,
    'patch.linewidth': 0.5,
    'xtick.major.width': 1.0,
    'ytick.major.width': 1.0,
    'xtick.minor.width': 0.5,
    'ytick.minor.width': 0.5,
    'axes.labelweight': 'normal',
    'axes.titleweight': 'normal',
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

# Academic-friendly color palette with distinct colors for differentiation
COLORS = {
    'two_colors': ['#2C3E50', '#E74C3C'],  # Dark blue-gray and red for 2 testees
    'three_colors': ['#2C3E50', '#E74C3C', '#27AE60'],  # Blue-gray, red, green for 3
    'four_colors': ['#2C3E50', '#E74C3C', '#27AE60', '#F39C12'],  # Blue-gray, red, green, orange for 4
    'many_colors': ['#2C3E50', '#E74C3C', '#27AE60', '#F39C12', '#3498DB', '#9B59B6', '#1ABC9C', '#E67E22'],  # Extended palette
    'pattern': ['///', '\\\\\\', '|||', '---'],  # Hatching patterns
}

def get_color_scheme(n_testees: int) -> list:
    """Get appropriate color scheme based on number of testees."""
    if n_testees == 2:
        return COLORS['two_colors']
    elif n_testees == 3:
        return COLORS['three_colors']
    elif n_testees == 4:
        return COLORS['four_colors']
    else:
        return COLORS['many_colors'][:n_testees]

def load_analysis_results(filepath: str) -> Dict[str, Any]:
    """Load analysis results from a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def setup_academic_style(ax, title: str, ylabel: str):
    """Apply professional academic styling to axes."""
    ax.set_title(title, fontweight='bold', pad=15)
    ax.set_ylabel(ylabel, fontweight='normal')
    ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.3, color='gray')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.0)
    ax.spines['bottom'].set_linewidth(1.0)
    ax.tick_params(axis='both', which='major', length=5, width=1.0)
    ax.tick_params(axis='both', which='minor', length=3, width=0.5)

def create_overall_comparison_chart(data: Dict[str, Any], output_dir: str):
    """Create a bar chart comparing overall scores of testees."""
    print("Creating overall comparison chart...")
    
    score_comparison = data.get("score_comparison", {}).get("testee_scores", {})
    if not score_comparison:
        print("No score comparison data found.")
        return

    testees = list(score_comparison.keys())
    metrics = ["completeness", "robustness", "syntactic_validity", "final_score"]
    
    # Clean metric labels for display
    metric_labels = {
        "completeness": "Completeness",
        "robustness": "Robustness",
        "syntactic_validity": "Syntactic Validity",
        "final_score": "Final Score"
    }
    
    x = np.arange(len(metrics))
    n_testees = len(testees)
    width = 0.75 / n_testees  # Adjust width based on number of testees
    spacing = width * 0.1  # Small spacing between bars
    
    fig, ax = plt.subplots(figsize=(9, 5.5))
    
    # Use distinct color scheme
    colors = get_color_scheme(n_testees)
    
    for i, testee in enumerate(testees):
        scores = [score_comparison[testee].get(m, 0) for m in metrics]
        offset = (i - (n_testees - 1) / 2) * (width + spacing)
        rects = ax.bar(x + offset, scores, width, 
                      label=testee.replace('_', ' ').title(),
                      color=colors[i],
                      edgecolor='black',
                      linewidth=0.8,
                      alpha=0.85)
        
        # Add value labels with better formatting
        ax.bar_label(rects, padding=2, fmt='%.2f', fontsize=9, fontweight='normal')

    setup_academic_style(ax, 'Overall Performance Comparison', 'Score')
    ax.set_xticks(x)
    ax.set_xticklabels([metric_labels.get(m, m.replace('_', ' ').title()) for m in metrics])
    ax.legend(frameon=True, fancybox=False, shadow=False, edgecolor='black', framealpha=0.9)
    ax.set_ylim(0, 1.1)
    ax.set_yticks(np.arange(0, 1.2, 0.2))
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'overall_comparison.png'), format='png', dpi=300)
    plt.savefig(os.path.join(output_dir, 'overall_comparison.pdf'), format='pdf')
    plt.close()

def create_property_breakdown_chart(data: Dict[str, Any], output_dir: str):
    """Create charts for property-specific performance."""
    print("Creating property breakdown charts...")
    
    property_breakdown = data.get("property_breakdown", {})
    if not property_breakdown:
        print("No property breakdown data found.")
        return

    metrics = ["completeness", "robustness", "syntactic_validity", "final_score"]
    
    # Clean metric labels for display
    metric_labels = {
        "completeness": "Completeness",
        "robustness": "Robustness",
        "syntactic_validity": "Syntactic Validity",
        "final_score": "Final Score"
    }
    
    for metric in metrics:
        fig, ax = plt.subplots(figsize=(10, 5.5))
        
        prop_types = list(property_breakdown.keys())
        testees = list(property_breakdown[prop_types[0]]["testee_stats"].keys())
        
        x = np.arange(len(prop_types))
        n_testees = len(testees)
        width = 0.75 / n_testees
        spacing = width * 0.1
        
        # Use distinct color scheme
        colors = get_color_scheme(n_testees)
        
        for i, testee in enumerate(testees):
            values = []
            for prop in prop_types:
                stats = property_breakdown[prop]["testee_stats"].get(testee, {}).get("aggregate_scores", {})
                values.append(stats.get(metric, 0))
            
            offset = (i - (n_testees - 1) / 2) * (width + spacing)
            rects = ax.bar(x + offset, values, width,
                          label=testee.replace('_', ' ').title(),
                          color=colors[i],
                          edgecolor='black',
                          linewidth=0.8,
                          alpha=0.85)
            ax.bar_label(rects, padding=2, fmt='%.2f', fontsize=9, fontweight='normal')
        
        title = f'{metric_labels.get(metric, metric.replace("_", " ").title())} by Property Type'
        setup_academic_style(ax, title, 'Score')
        ax.set_xticks(x)
        ax.set_xticklabels([p.replace('_', ' ').title() for p in prop_types], 
                          rotation=0, ha='center')
        ax.legend(frameon=True, fancybox=False, shadow=False, edgecolor='black', framealpha=0.9)
        ax.set_ylim(0, 1.1)
        ax.set_yticks(np.arange(0, 1.2, 0.2))
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f'property_breakdown_{metric}.png'), 
                   format='png', dpi=300)
        plt.savefig(os.path.join(output_dir, f'property_breakdown_{metric}.pdf'), 
                   format='pdf')
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

