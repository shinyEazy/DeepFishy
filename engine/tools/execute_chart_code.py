"""
Tool for executing dynamically generated chart code from the chart generator agent.
"""

import os
import uuid
import traceback
from datetime import datetime
from typing import Optional
from langchain_core.tools import tool

# Set up matplotlib for non-interactive backend
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Set Vietnamese font support
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


@tool
def execute_chart_code(
    code: str,
    chart_title: Optional[str] = None,
) -> str:
    """
    Execute Python matplotlib code to generate a chart image.

    This tool executes dynamically generated Python code that creates charts
    using matplotlib. The code should create a figure and plot data, but
    should NOT include plt.show() or plt.savefig() - these are handled automatically.

    Args:
        code: Python code that generates a matplotlib chart.
              The code should:
              - Import any needed libraries (numpy, pandas if needed)
              - Create figure with plt.figure() or plt.subplots()
              - Plot data using plt methods
              - Set labels, titles, legends as needed
              DO NOT include plt.show() or plt.savefig()
        chart_title: Optional title for the chart file (used in filename)

    Returns:
        Path to the saved chart image file, or error message if execution fails.

    Example:
        >>> execute_chart_code(
        ...     code='''
        ... import matplotlib.pyplot as plt
        ...
        ... data = {"Q1": 1500, "Q2": 1800, "Q3": 2000, "Q4": 2200}
        ... fig, ax = plt.subplots(figsize=(10, 6))
        ... ax.bar(data.keys(), data.values(), color='#2E86AB')
        ... ax.set_title('Doanh thu theo quý 2025')
        ... ax.set_ylabel('Tỷ VNĐ')
        ... ax.grid(axis='y', alpha=0.3)
        ... ''',
        ...     chart_title="revenue_quarterly"
        ... )
        'outputs/{session_id}/images/revenue_quarterly_20260122_143000_abc12345.png'
    """
    try:
        # Prepare output directory
        base_dir = os.getenv("OUTPUT_DIR", "results")
        charts_dir = os.path.join(base_dir, "images")
        os.makedirs(charts_dir, exist_ok=True)

        # Generate unique filename
        chart_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_slug = (chart_title or "chart").replace(" ", "_").lower()[:30]
        filename = f"{title_slug}_{timestamp}_{chart_id}.png"
        filepath = os.path.join(charts_dir, filename)

        # Close any existing figures to prevent memory issues
        plt.close("all")

        # Create a restricted execution namespace
        exec_namespace = {
            "__builtins__": __builtins__,
            "plt": plt,
            "matplotlib": matplotlib,
        }

        # Add common libraries if available
        try:
            import numpy as np

            exec_namespace["np"] = np
            exec_namespace["numpy"] = np
        except ImportError:
            pass

        try:
            import pandas as pd

            exec_namespace["pd"] = pd
            exec_namespace["pandas"] = pd
        except ImportError:
            pass

        # Execute the chart generation code
        exec(code, exec_namespace)

        # Get current figure and save
        fig = plt.gcf()
        if fig.get_axes():
            # Apply tight layout and save
            plt.tight_layout()
            plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
            plt.close("all")
            return filepath
        else:
            plt.close("all")
            return "Error: No figure was created by the provided code"

    except SyntaxError as e:
        return f"Syntax error in chart code: {str(e)}"
    except Exception as e:
        error_details = traceback.format_exc()
        return f"Error executing chart code: {str(e)}\n\nDetails:\n{error_details}"


__all__ = ["execute_chart_code"]
