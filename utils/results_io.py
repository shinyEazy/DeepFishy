"""Save and display benchmark evaluation results."""

import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def save_results(results: dict, results_dir: str) -> str:
    """Save evaluation results to a timestamped JSON file."""
    output_dir = PROJECT_ROOT / results_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{timestamp}_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return str(output_path)


def print_results_table(results: dict):
    """Print a formatted summary table of evaluation results."""
    evaluations = results.get("evaluations", [])
    if not evaluations:
        print("No evaluations found.")
        return

    dimensions = [
        "cons",
        "faith",
        "t_i",
        "rich",
        "cover",
        "ins",
        "logic",
        "lang",
        "vis",
    ]
    dim_short = ["Cons", "Faith", "T-I", "Rich", "Cover", "Ins", "Logic", "Lang", "Vis"]

    header = (
        f"{'Report ID':<30} " + " ".join(f"{d:>5}" for d in dim_short) + f" {'AVG':>8}"
    )
    print("\n" + "=" * len(header))
    print("BENCHMARK EVALUATION RESULTS")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for ev in evaluations:
        report_id = ev.get("report_id", "unknown")
        if len(report_id) > 28:
            report_id = "..." + report_id[-25:]

        scores_dict = ev.get("scores", {})
        scores = []
        for dim in dimensions:
            s = scores_dict.get(dim, {}).get("score", "-")
            scores.append(f"{s:>5}")

        avg = ev.get("overall_average", "-")
        avg_str = f"{avg:>8.2f}" if isinstance(avg, (int, float)) else f"{avg:>8}"
        print(f"{report_id:<30} " + " ".join(scores) + f" {avg_str}")

    print("=" * len(header))
