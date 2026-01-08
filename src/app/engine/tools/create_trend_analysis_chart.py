"""
Tool for creating trend analysis charts with forecasting capabilities.
"""

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import List, Optional
from langchain_core.tools import tool
from datetime import datetime
import uuid
import numpy as np

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False


@tool
def create_trend_analysis_chart(
    title: str,
    dates: List[str],
    values: List[float],
    ylabel: str = "Giá trị",
    show_trend_line: bool = True,
    moving_average_window: Optional[int] = None,
) -> str:
    """
    Tạo biểu đồ phân tích xu hướng với đường xu hướng và trung bình động.

    Args:
        title: Tiêu đề biểu đồ
        dates: Danh sách các nhãn thời gian (có thể là ngày, tháng, quý, năm)
               Ví dụ: ["2024-01", "2024-02", "2024-03", ...]
        values: Danh sách giá trị tương ứng với các mốc thời gian
                Ví dụ: [1000, 1050, 1100, 1080, 1150, ...]
        ylabel: Nhãn trục y
        show_trend_line: Có hiển thị đường xu hướng (trend line) hay không
        moving_average_window: Số kỳ để tính trung bình động (None = không hiển thị)
                              Ví dụ: 3 = trung bình động 3 kỳ

    Returns:
        Đường dẫn tới file ảnh biểu đồ đã tạo

    Example:
        >>> create_trend_analysis_chart(
        ...     title="Phân tích xu hướng giá cổ phiếu",
        ...     dates=["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"],
        ...     values=[100, 105, 110, 108, 115, 120],
        ...     ylabel="Giá (nghìn VNĐ)",
        ...     show_trend_line=True,
        ...     moving_average_window=3
        ... )
        'results/charts/trend_abc123.png'
    """
    try:
        # Create charts directory
        charts_dir = os.path.join("results", "charts")
        os.makedirs(charts_dir, exist_ok=True)

        # Generate unique filename
        chart_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trend_{timestamp}_{chart_id}.png"
        filepath = os.path.join(charts_dir, filename)

        # Create figure
        fig, ax = plt.subplots(figsize=(14, 7))

        x = range(len(dates))

        # Plot actual values
        ax.plot(
            x,
            values,
            marker="o",
            linewidth=2.5,
            markersize=8,
            color="#2E86AB",
            label="Giá trị thực tế",
            markerfacecolor="#4ECDC4",
            markeredgewidth=2,
        )

        # Add value labels on key points (first, last, min, max)
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))
        key_points = [0, len(values) - 1, max_idx, min_idx]

        for i in set(key_points):
            ax.text(
                i,
                values[i],
                f"{values[i]:,.0f}",
                ha="center",
                va="bottom" if i != max_idx else "top",
                fontsize=9,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7),
            )

        # Add trend line
        if show_trend_line and len(values) > 2:
            z = np.polyfit(x, values, 1)
            p = np.poly1d(z)
            ax.plot(
                x, p(x), "--", linewidth=2, color="#E63946", label="Xu hướng", alpha=0.7
            )

            # Calculate and display trend
            slope = z[0]
            trend_text = "Xu hướng tăng" if slope > 0 else "Xu hướng giảm"
            change_pct = (
                (slope / values[0]) * 100 * len(values) if values[0] != 0 else 0
            )
            ax.text(
                0.02,
                0.98,
                f"{trend_text}\n({change_pct:+.1f}%)",
                transform=ax.transAxes,
                fontsize=10,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

        # Add moving average
        if (
            moving_average_window
            and moving_average_window > 1
            and len(values) >= moving_average_window
        ):
            ma = []
            for i in range(len(values)):
                if i < moving_average_window - 1:
                    ma.append(None)
                else:
                    window_values = values[i - moving_average_window + 1 : i + 1]
                    ma.append(sum(window_values) / moving_average_window)

            # Plot moving average (skip None values)
            ma_x = [i for i in range(len(ma)) if ma[i] is not None]
            ma_values = [v for v in ma if v is not None]

            ax.plot(
                ma_x,
                ma_values,
                linewidth=2,
                color="#F18F01",
                label=f"Trung bình động {moving_average_window} kỳ",
                alpha=0.7,
            )

        # Formatting
        ax.set_xticks(x)
        ax.set_xticklabels(dates)
        ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(loc="best", frameon=True, shadow=True, fontsize=10)

        # Rotate x-axis labels if needed
        if len(dates) > 8:
            plt.xticks(rotation=45, ha="right")

        # Add statistics box
        stats_text = f"Cao nhất: {max(values):,.0f}\n"
        stats_text += f"Thấp nhất: {min(values):,.0f}\n"
        stats_text += f"Trung bình: {sum(values)/len(values):,.0f}\n"
        change = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
        stats_text += f"Thay đổi: {change:+.1f}%"

        ax.text(
            0.98,
            0.02,
            stats_text,
            transform=ax.transAxes,
            fontsize=9,
            verticalalignment="bottom",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.5),
        )

        plt.tight_layout()
        plt.savefig(filepath, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        return filepath

    except Exception as e:
        return f"Error creating trend analysis chart: {str(e)}"
