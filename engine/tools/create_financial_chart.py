"""
Tool for creating financial charts and visualizations.
"""

import os
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
from typing import Dict, Literal, Optional
from langchain_core.tools import tool
from datetime import datetime
import uuid

# Set Vietnamese font support
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


@tool
def create_financial_chart(
    title: str,
    data: Dict[str, float],
    chart_type: Literal["bar", "line", "pie"] = "bar",
    ylabel: str = "Giá trị",
    xlabel: str = "",
    color_scheme: str = "professional",
) -> str:
    """
    Tạo biểu đồ tài chính cơ bản với dữ liệu đơn giản.

    Args:
        title: Tiêu đề biểu đồ
        data: Dictionary với key là nhãn và value là giá trị số
              Ví dụ: {"Q1 2024": 1500000, "Q2 2024": 1800000, "Q3 2024": 2000000}
        chart_type: Loại biểu đồ - "bar" (cột), "line" (đường), "pie" (tròn)
        ylabel: Nhãn trục y (cho bar/line chart)
        xlabel: Nhãn trục x (cho bar/line chart)
        color_scheme: Bảng màu sử dụng - "professional", "vibrant", "pastel"

    Returns:
        Đường dẫn tới file ảnh biểu đồ đã tạo

    Example:
        >>> create_financial_chart(
        ...     title="Doanh thu theo quý",
        ...     data={"Q1": 1500, "Q2": 1800, "Q3": 2000},
        ...     chart_type="bar",
        ...     ylabel="Doanh thu (tỷ VNĐ)"
        ... )
        'outputs/{session_id}/images/chart_20260113_140000_abc12345.png'
    """
    try:
        # Create charts directory - use OUTPUT_DIR env var if available (for session-based paths)
        # Falls back to results/charts if not set
        base_dir = os.getenv("OUTPUT_DIR", "results")
        charts_dir = os.path.join(base_dir, "images")
        os.makedirs(charts_dir, exist_ok=True)

        # Generate unique filename
        chart_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chart_{timestamp}_{chart_id}.png"
        filepath = os.path.join(charts_dir, filename)

        # Color schemes
        color_schemes = {
            "professional": ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"],
            "vibrant": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"],
            "pastel": ["#A8DADC", "#457B9D", "#E63946", "#F1FAEE", "#1D3557"],
        }
        colors = color_schemes.get(color_scheme, color_schemes["professional"])

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))

        labels = list(data.keys())
        values = list(data.values())

        if chart_type == "bar":
            bars = ax.bar(
                labels,
                values,
                color=colors[: len(labels)],
                alpha=0.8,
                edgecolor="white",
                linewidth=1.5,
            )
            ax.set_ylabel(ylabel, fontsize=11, fontweight="bold")
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
            ax.grid(axis="y", alpha=0.3, linestyle="--")

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{height:,.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        elif chart_type == "line":
            ax.plot(
                labels,
                values,
                marker="o",
                linewidth=2.5,
                markersize=8,
                color=colors[0],
                markerfacecolor=colors[1],
                markeredgewidth=2,
            )
            ax.set_ylabel(ylabel, fontsize=11, fontweight="bold")
            if xlabel:
                ax.set_xlabel(xlabel, fontsize=11, fontweight="bold")
            ax.grid(True, alpha=0.3, linestyle="--")

            # Add value labels on points
            for i, (label, value) in enumerate(zip(labels, values)):
                ax.text(i, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9)

        elif chart_type == "pie":
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                colors=colors[: len(labels)],
                startangle=90,
                textprops={"fontsize": 10},
            )
            # Make percentage text bold
            for autotext in autotexts:
                autotext.set_color("white")
                autotext.set_fontweight("bold")
                autotext.set_fontsize(10)
            ax.axis("equal")

        # Set title
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

        # Rotate x-axis labels if needed
        if chart_type in ["bar", "line"] and len(labels) > 5:
            plt.xticks(rotation=45, ha="right")

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Save figure
        plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        return filepath

    except Exception as e:
        return f"Error creating chart: {str(e)}"


# Make the tool available for import
__all__ = ["create_financial_chart"]
