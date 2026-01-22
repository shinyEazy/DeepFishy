"""
Tool for creating comparison charts with multiple datasets.
"""

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import List, Dict, Any
from langchain_core.tools import tool
from datetime import datetime
import uuid

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


@tool
def create_comparison_chart(
    title: str,
    categories: List[str],
    datasets: List[Dict[str, Any]],
    ylabel: str = "Giá trị",
    xlabel: str = "",
    chart_type: str = "grouped_bar",
) -> str:
    """
    Tạo biểu đồ so sánh nhiều bộ dữ liệu (ví dụ: so sánh giữa các năm, các sản phẩm).

    Args:
        title: Tiêu đề biểu đồ
        categories: Danh sách các danh mục/nhãn trên trục X
                   Ví dụ: ["Q1", "Q2", "Q3", "Q4"]
        datasets: Danh sách các bộ dữ liệu để so sánh, mỗi bộ có dạng:
                 {"label": "Tên bộ dữ liệu", "data": [giá trị 1, giá trị 2, ...]}
                 Ví dụ: [
                     {"label": "2023", "data": [100, 120, 130, 140]},
                     {"label": "2024", "data": [110, 135, 145, 160]}
                 ]
        ylabel: Nhãn trục y
        xlabel: Nhãn trục x
        chart_type: Loại biểu đồ - "grouped_bar" (cột nhóm), "line" (đường), "stacked_bar" (cột xếp chồng)

    Returns:
        Đường dẫn tới file ảnh biểu đồ đã tạo

    Example:
        >>> create_comparison_chart(
        ...     title="So sánh doanh thu 2023-2024",
        ...     categories=["Q1", "Q2", "Q3", "Q4"],
        ...     datasets=[
        ...         {"label": "2023", "data": [1500, 1600, 1700, 1800]},
        ...         {"label": "2024", "data": [1600, 1800, 1900, 2100]}
        ...     ],
        ...     ylabel="Doanh thu (tỷ VNĐ)"
        ... )
        'outputs/{session_id}/images/comparison_20260113_140000_abc12345.png'
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
        filename = f"comparison_{timestamp}_{chart_id}.png"
        filepath = os.path.join(charts_dir, filename)

        # Color palette
        colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E", "#4ECDC4"]

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 7))

        if chart_type == "grouped_bar":
            x = range(len(categories))
            width = 0.8 / len(datasets)

            for i, dataset in enumerate(datasets):
                offset = (i - len(datasets) / 2 + 0.5) * width
                bars = ax.bar(
                    [p + offset for p in x],
                    dataset["data"],
                    width,
                    label=dataset["label"],
                    color=colors[i % len(colors)],
                    alpha=0.8,
                )

                # Add value labels
                for bar in bars:
                    height = bar.get_height()
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height,
                        f"{height:,.0f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.grid(axis="y", alpha=0.3, linestyle="--")

        elif chart_type == "stacked_bar":
            x = range(len(categories))
            bottom = [0] * len(categories)

            for i, dataset in enumerate(datasets):
                bars = ax.bar(
                    x,
                    dataset["data"],
                    label=dataset["label"],
                    color=colors[i % len(colors)],
                    alpha=0.8,
                    bottom=bottom,
                )

                # Update bottom for stacking
                bottom = [b + d for b, d in zip(bottom, dataset["data"])]

            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.grid(axis="y", alpha=0.3, linestyle="--")

        elif chart_type == "line":
            for i, dataset in enumerate(datasets):
                ax.plot(
                    categories,
                    dataset["data"],
                    marker="o",
                    linewidth=2.5,
                    markersize=8,
                    label=dataset["label"],
                    color=colors[i % len(colors)],
                )

                # Add value labels
                for j, value in enumerate(dataset["data"]):
                    ax.text(
                        j,
                        value,
                        f"{value:,.0f}",
                        ha="center",
                        va="bottom" if i % 2 == 0 else "top",
                        fontsize=8,
                    )

            ax.grid(True, alpha=0.3, linestyle="--")

        # Labels and title
        ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
        if xlabel:
            ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

        # Legend
        ax.legend(loc="upper left", frameon=True, shadow=True, fontsize=10)

        # Rotate x-axis labels if needed
        if len(categories) > 8:
            plt.xticks(rotation=45, ha="right")

        plt.tight_layout()
        plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        return filepath

    except Exception as e:
        return f"Error creating comparison chart: {str(e)}"


__all__ = ["create_comparison_chart"]
