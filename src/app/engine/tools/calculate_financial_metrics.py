"""
Tool for calculating common financial metrics and ratios.
"""

from typing import Dict, Optional, Any
from langchain_core.tools import tool


@tool
def calculate_financial_metrics(
    revenue: Optional[float] = None,
    net_income: Optional[float] = None,
    total_assets: Optional[float] = None,
    total_equity: Optional[float] = None,
    total_liabilities: Optional[float] = None,
    current_assets: Optional[float] = None,
    current_liabilities: Optional[float] = None,
    operating_income: Optional[float] = None,
    interest_expense: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
    market_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Tính toán các chỉ số tài chính quan trọng từ dữ liệu đầu vào.

    Args:
        revenue: Doanh thu
        net_income: Lợi nhuận sau thuế
        total_assets: Tổng tài sản
        total_equity: Vốn chủ sở hữu
        total_liabilities: Tổng nợ phải trả
        current_assets: Tài sản ngắn hạn
        current_liabilities: Nợ ngắn hạn
        operating_income: Lợi nhuận hoạt động
        interest_expense: Chi phí lãi vay
        shares_outstanding: Số cổ phiếu đang lưu hành
        market_price: Giá thị trường mỗi cổ phiếu

    Returns:
        Dictionary chứa các chỉ số tài chính đã tính toán với giải thích

    Example:
        >>> calculate_financial_metrics(
        ...     revenue=1000000,
        ...     net_income=150000,
        ...     total_assets=2000000,
        ...     total_equity=800000
        ... )
        {
            'profitability': {
                'net_profit_margin': {'value': 15.0, 'unit': '%', 'interpretation': '...'},
                'roa': {'value': 7.5, 'unit': '%', 'interpretation': '...'},
                'roe': {'value': 18.75, 'unit': '%', 'interpretation': '...'}
            },
            ...
        }
    """
    results = {
        "profitability": {},
        "liquidity": {},
        "leverage": {},
        "efficiency": {},
        "valuation": {},
        "summary": [],
    }

    # === PROFITABILITY RATIOS (Chỉ số sinh lời) ===

    # Net Profit Margin (Tỷ suất lợi nhuận ròng)
    if revenue and net_income and revenue > 0:
        npm = (net_income / revenue) * 100
        results["profitability"]["net_profit_margin"] = {
            "name": "Tỷ suất lợi nhuận ròng",
            "value": round(npm, 2),
            "unit": "%",
            "formula": "(Lợi nhuận sau thuế / Doanh thu) × 100",
            "interpretation": _interpret_npm(npm),
        }
        results["summary"].append(f"Tỷ suất lợi nhuận ròng: {npm:.2f}%")

    # Return on Assets (ROA - Tỷ suất sinh lời trên tài sản)
    if net_income and total_assets and total_assets > 0:
        roa = (net_income / total_assets) * 100
        results["profitability"]["roa"] = {
            "name": "ROA - Tỷ suất sinh lời trên tài sản",
            "value": round(roa, 2),
            "unit": "%",
            "formula": "(Lợi nhuận sau thuế / Tổng tài sản) × 100",
            "interpretation": _interpret_roa(roa),
        }
        results["summary"].append(f"ROA: {roa:.2f}%")

    # Return on Equity (ROE - Tỷ suất sinh lời trên vốn chủ sở hữu)
    if net_income and total_equity and total_equity > 0:
        roe = (net_income / total_equity) * 100
        results["profitability"]["roe"] = {
            "name": "ROE - Tỷ suất sinh lời trên vốn chủ sở hữu",
            "value": round(roe, 2),
            "unit": "%",
            "formula": "(Lợi nhuận sau thuế / Vốn chủ sở hữu) × 100",
            "interpretation": _interpret_roe(roe),
        }
        results["summary"].append(f"ROE: {roe:.2f}%")

    # Operating Margin (Tỷ suất lợi nhuận hoạt động)
    if operating_income and revenue and revenue > 0:
        om = (operating_income / revenue) * 100
        results["profitability"]["operating_margin"] = {
            "name": "Tỷ suất lợi nhuận hoạt động",
            "value": round(om, 2),
            "unit": "%",
            "formula": "(Lợi nhuận hoạt động / Doanh thu) × 100",
            "interpretation": _interpret_operating_margin(om),
        }

    # === LIQUIDITY RATIOS (Chỉ số thanh khoản) ===

    # Current Ratio (Tỷ số thanh toán hiện hành)
    if current_assets and current_liabilities and current_liabilities > 0:
        cr = current_assets / current_liabilities
        results["liquidity"]["current_ratio"] = {
            "name": "Tỷ số thanh toán hiện hành",
            "value": round(cr, 2),
            "unit": "lần",
            "formula": "Tài sản ngắn hạn / Nợ ngắn hạn",
            "interpretation": _interpret_current_ratio(cr),
        }
        results["summary"].append(f"Tỷ số thanh toán hiện hành: {cr:.2f}")

    # === LEVERAGE RATIOS (Chỉ số đòn bẩy) ===

    # Debt-to-Equity Ratio (Tỷ số nợ trên vốn chủ sở hữu)
    if total_liabilities and total_equity and total_equity > 0:
        de = total_liabilities / total_equity
        results["leverage"]["debt_to_equity"] = {
            "name": "Tỷ số nợ trên vốn chủ sở hữu",
            "value": round(de, 2),
            "unit": "lần",
            "formula": "Tổng nợ / Vốn chủ sở hữu",
            "interpretation": _interpret_debt_to_equity(de),
        }
        results["summary"].append(f"Tỷ số nợ/vốn: {de:.2f}")

    # Debt-to-Assets Ratio (Tỷ số nợ trên tài sản)
    if total_liabilities and total_assets and total_assets > 0:
        da = (total_liabilities / total_assets) * 100
        results["leverage"]["debt_to_assets"] = {
            "name": "Tỷ số nợ trên tài sản",
            "value": round(da, 2),
            "unit": "%",
            "formula": "(Tổng nợ / Tổng tài sản) × 100",
            "interpretation": _interpret_debt_to_assets(da),
        }

    # Interest Coverage Ratio (Khả năng thanh toán lãi vay)
    if operating_income and interest_expense and interest_expense > 0:
        icr = operating_income / interest_expense
        results["leverage"]["interest_coverage"] = {
            "name": "Khả năng thanh toán lãi vay",
            "value": round(icr, 2),
            "unit": "lần",
            "formula": "Lợi nhuận hoạt động / Chi phí lãi vay",
            "interpretation": _interpret_interest_coverage(icr),
        }

    # === EFFICIENCY RATIOS (Chỉ số hiệu quả) ===

    # Asset Turnover (Vòng quay tài sản)
    if revenue and total_assets and total_assets > 0:
        at = revenue / total_assets
        results["efficiency"]["asset_turnover"] = {
            "name": "Vòng quay tài sản",
            "value": round(at, 2),
            "unit": "lần",
            "formula": "Doanh thu / Tổng tài sản",
            "interpretation": _interpret_asset_turnover(at),
        }

    # === VALUATION RATIOS (Chỉ số định giá) ===

    # Earnings Per Share (EPS - Lãi cơ bản trên cổ phiếu)
    if net_income and shares_outstanding and shares_outstanding > 0:
        eps = net_income / shares_outstanding
        results["valuation"]["eps"] = {
            "name": "EPS - Lãi cơ bản trên cổ phiếu",
            "value": round(eps, 2),
            "unit": "VNĐ/cổ phiếu",
            "formula": "Lợi nhuận sau thuế / Số cổ phiếu lưu hành",
            "interpretation": f"Mỗi cổ phiếu tạo ra {eps:.2f} VNĐ lợi nhuận",
        }

        # Price-to-Earnings Ratio (P/E)
        if market_price and eps > 0:
            pe = market_price / eps
            results["valuation"]["pe_ratio"] = {
                "name": "P/E - Hệ số giá trên thu nhập",
                "value": round(pe, 2),
                "unit": "lần",
                "formula": "Giá thị trường / EPS",
                "interpretation": _interpret_pe_ratio(pe),
            }
            results["summary"].append(f"P/E: {pe:.2f}")

    # Market Capitalization (Vốn hóa thị trường)
    if market_price and shares_outstanding:
        market_cap = market_price * shares_outstanding
        results["valuation"]["market_cap"] = {
            "name": "Vốn hóa thị trường",
            "value": round(market_cap, 2),
            "unit": "VNĐ",
            "formula": "Giá thị trường × Số cổ phiếu lưu hành",
            "interpretation": f"Vốn hóa: {_format_large_number(market_cap)} VNĐ",
        }

    return results


# === INTERPRETATION FUNCTIONS ===


def _interpret_npm(npm: float) -> str:
    if npm >= 20:
        return "Rất tốt - Công ty có khả năng sinh lời cao"
    elif npm >= 10:
        return "Tốt - Khả năng sinh lời ở mức khá"
    elif npm >= 5:
        return "Trung bình - Khả năng sinh lời ở mức chấp nhận được"
    elif npm > 0:
        return "Thấp - Công ty có lợi nhuận nhưng biên lợi nhuận thấp"
    else:
        return "Âm - Công ty đang thua lỗ"


def _interpret_roa(roa: float) -> str:
    if roa >= 10:
        return "Rất tốt - Tài sản được sử dụng hiệu quả cao"
    elif roa >= 5:
        return "Tốt - Hiệu quả sử dụng tài sản ở mức khá"
    elif roa >= 2:
        return "Trung bình - Hiệu quả sử dụng tài sản chấp nhận được"
    else:
        return "Thấp - Tài sản chưa được tận dụng hiệu quả"


def _interpret_roe(roe: float) -> str:
    if roe >= 20:
        return "Rất tốt - Sinh lời cao cho cổ đông"
    elif roe >= 15:
        return "Tốt - Sinh lời tốt cho cổ đông"
    elif roe >= 10:
        return "Trung bình - Sinh lời ở mức chấp nhận được"
    elif roe > 0:
        return "Thấp - Sinh lời thấp cho cổ đông"
    else:
        return "Âm - Công ty đang thua lỗ"


def _interpret_operating_margin(om: float) -> str:
    if om >= 15:
        return "Rất tốt - Hoạt động kinh doanh hiệu quả cao"
    elif om >= 10:
        return "Tốt - Hoạt động kinh doanh hiệu quả"
    elif om >= 5:
        return "Trung bình - Hiệu quả hoạt động chấp nhận được"
    else:
        return "Thấp - Cần cải thiện hiệu quả hoạt động"


def _interpret_current_ratio(cr: float) -> str:
    if cr >= 2:
        return "Rất tốt - Khả năng thanh toán ngắn hạn mạnh"
    elif cr >= 1.5:
        return "Tốt - Khả năng thanh toán ngắn hạn tốt"
    elif cr >= 1:
        return "Chấp nhận được - Đủ khả năng thanh toán nợ ngắn hạn"
    else:
        return "Rủi ro - Có thể gặp khó khăn trong thanh toán nợ ngắn hạn"


def _interpret_debt_to_equity(de: float) -> str:
    if de <= 0.5:
        return "Thấp - Ít sử dụng đòn bẩy tài chính, rủi ro thấp"
    elif de <= 1:
        return "Trung bình - Cơ cấu vốn cân bằng"
    elif de <= 2:
        return "Cao - Sử dụng nhiều nợ, cần theo dõi"
    else:
        return "Rất cao - Rủi ro tài chính cao, phụ thuộc nhiều vào nợ"


def _interpret_debt_to_assets(da: float) -> str:
    if da <= 30:
        return "Thấp - Tỷ lệ nợ an toàn"
    elif da <= 50:
        return "Trung bình - Tỷ lệ nợ hợp lý"
    elif da <= 70:
        return "Cao - Cần chú ý đến khả năng trả nợ"
    else:
        return "Rất cao - Rủi ro tài chính đáng kể"


def _interpret_interest_coverage(icr: float) -> str:
    if icr >= 5:
        return "Rất tốt - Dễ dàng thanh toán lãi vay"
    elif icr >= 3:
        return "Tốt - Đủ khả năng thanh toán lãi vay"
    elif icr >= 1.5:
        return "Chấp nhận được - Có thể thanh toán lãi vay"
    else:
        return "Rủi ro - Khó khăn trong việc thanh toán lãi vay"


def _interpret_asset_turnover(at: float) -> str:
    if at >= 2:
        return "Rất tốt - Tài sản tạo doanh thu hiệu quả cao"
    elif at >= 1:
        return "Tốt - Tài sản tạo doanh thu hiệu quả"
    elif at >= 0.5:
        return "Trung bình - Hiệu quả sử dụng tài sản chấp nhận được"
    else:
        return "Thấp - Tài sản chưa tạo doanh thu hiệu quả"


def _interpret_pe_ratio(pe: float) -> str:
    if pe <= 10:
        return "Thấp - Có thể bị định giá thấp hoặc triển vọng hạn chế"
    elif pe <= 20:
        return "Trung bình - Định giá hợp lý"
    elif pe <= 30:
        return "Cao - Kỳ vọng tăng trưởng cao hoặc có thể bị định giá cao"
    else:
        return "Rất cao - Kỳ vọng tăng trưởng rất cao hoặc có dấu hiệu bong bóng"


def _format_large_number(num: float) -> str:
    """Format large numbers with appropriate units (nghìn, triệu, tỷ)"""
    if num >= 1_000_000_000_000:
        return f"{num/1_000_000_000_000:.2f} nghìn tỷ"
    elif num >= 1_000_000_000:
        return f"{num/1_000_000_000:.2f} tỷ"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.2f} triệu"
    elif num >= 1_000:
        return f"{num/1_000:.2f} nghìn"
    else:
        return f"{num:.2f}"


__all__ = ["calculate_financial_metrics"]
