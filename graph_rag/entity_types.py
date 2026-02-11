"""
Custom Entity and Edge Types for Vietnamese Financial Market Knowledge Graph.

This module defines the ontology for the Deep Research workflow:
- 5 Core Entity Types (Nodes)
- 8 Edge Types (Relationships) for Causal Graph analysis

All types are designed for:
1. Traceability (source_url, extraction_date)
2. Causal Analysis (MarketEvent -> MarketEvent)
3. Cross-ownership detection (PublicCompany -> PublicCompany)
4. Impact analysis (MacroIndicator -> PublicCompany)

DESIGN NOTES:
- MarketEvent is the CORE causal node (not Company-centric)
- Uses Enums to prevent string variations ("HOSE" vs "hose")
- major_shareholders removed - use Owns edge instead
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# =============================================================================
# ENUMS - Preventing string variations, ensuring consistent values
# =============================================================================


class EventType(str, Enum):
    """Types of market events"""

    POLICY = "Chính sách vĩ mô"
    SCANDAL = "Tin đồn/Bắt bớ"
    EARNINGS = "Báo cáo tài chính"
    MERGER = "M&A"
    DIVIDEND = "Cổ tức"
    REGULATORY = "Quy định mới"
    MARKET_MOVEMENT = "Biến động thị trường"
    MACRO_CHANGE = "Thay đổi vĩ mô"


class EventStatus(str, Enum):
    """Status of an event - distinguishes announcement from actual event"""

    ANNOUNCED = "ANNOUNCED"  # Tin ra: "NHNN dự kiến hạ lãi suất"
    CONFIRMED = "CONFIRMED"  # Xác nhận: "NHNN sẽ hạ lãi suất"
    IMPLEMENTED = "IMPLEMENTED"  # Thực hiện: "NHNN đã hạ lãi suất"


class EventScope(str, Enum):
    """Scope of event impact - crucial for causal chain reasoning"""

    MARKET = "MARKET"  # Toàn thị trường (e.g., Fed rate hike)
    SECTOR = "SECTOR"  # Ngành cụ thể (e.g., Real estate law)
    COMPANY = "COMPANY"  # Công ty cụ thể (e.g., VIC earnings)


class Exchange(str, Enum):
    """Vietnamese stock exchanges"""

    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"


class Sentiment(str, Enum):
    """Market sentiment"""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class ImpactLevel(str, Enum):
    """Impact level of events"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Trend(str, Enum):
    """Trend direction"""

    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"


class MetricType(str, Enum):
    """Type of financial metric - prevents comparing apples to oranges"""

    FLOW = "FLOW"  # Revenue, Profit (time-period based)
    STOCK = "STOCK"  # Debt, Assets (point-in-time)
    MARKET = "MARKET"  # Stock Price, Market Cap
    RATIO = "RATIO"  # P/E, ROE, NIM


# =============================================================================
# ENTITY TYPES (5 Core Nodes)
# =============================================================================


class PublicCompany(BaseModel):
    """
    Doanh nghiệp Niêm yết - A publicly traded company on Vietnamese exchanges.

    NOTE: major_shareholders removed - use Owns edge instead for proper ontology.
    """

    company_name: str = Field(
        ..., description="Full legal name, e.g., 'Công ty CP Tập đoàn Hòa Phát'"
    )
    ticker: str = Field(..., description="3-letter stock code, e.g., 'HPG'")
    exchange: Optional[Exchange] = Field(None, description="HOSE, HNX, or UPCOM")
    industry: Optional[str] = Field(
        None, description="e.g., 'Thép', 'Bất động sản', 'Ngân hàng'"
    )
    # Traceability fields
    source_url: Optional[str] = Field(None, description="URL of the source article")
    extraction_date: Optional[str] = Field(None, description="ISO date when extracted")


class FinancialMetric(BaseModel):
    """
    Chỉ số Tài chính - Structured financial metrics for comparison.

    metric_type prevents agent from comparing wrong types (e.g., Revenue vs Debt).
    """

    metric_name: str = Field(
        ..., description="e.g., 'Doanh thu thuần', 'Lợi nhuận sau thuế', 'NIM'"
    )
    metric_type: Optional[MetricType] = Field(
        None, description="FLOW/STOCK/MARKET/RATIO"
    )
    value: Optional[float] = Field(None, description="Numerical value")
    unit: Optional[str] = Field(None, description="e.g., 'tỷ VNĐ', 'phần trăm'")
    period: Optional[str] = Field(
        None, description="Time period, e.g., 'Q3/2024', 'Năm 2023'"
    )
    yoy_change: Optional[float] = Field(
        None, description="Year-over-Year growth percentage"
    )
    # Traceability
    source_url: Optional[str] = Field(None, description="URL of the source article")
    extraction_date: Optional[str] = Field(None, description="ISO date when extracted")


class KeyPerson(BaseModel):
    """
    Nhân sự Chủ chốt - Key executives and board members.

    In Vietnam, the reputation of the "Captain" heavily influences stock price.
    """

    full_name: str = Field(..., description="e.g., 'Trần Đình Long', 'Phạm Nhật Vượng'")
    current_role: Optional[str] = Field(
        None, description="e.g., 'Chủ tịch HĐQT', 'Tổng Giám đốc'"
    )
    reputation_status: Optional[str] = Field(
        None, description="e.g., 'Uy tín', 'Đang bị điều tra', 'Liên quan tin đồn'"
    )
    nationality: Optional[str] = Field(default="Vietnam")
    # Traceability
    source_url: Optional[str] = Field(None, description="URL of the source article")
    extraction_date: Optional[str] = Field(None, description="ISO date when extracted")


class MarketEvent(BaseModel):
    """
    Sự kiện Thị trường - The CORE causal node for Deep Research.

    This is the most important entity. Captures "What happened" and enables
    causal chain analysis (Event A -> Event B -> Event C).

    KEY DESIGN: Event-centric, not Company-centric.
    """

    title: str = Field(
        ..., description="Short summary, e.g., 'Ngân hàng Nhà nước hạ lãi suất'"
    )
    event_type: Optional[EventType] = Field(None, description="Type of event")
    event_status: Optional[EventStatus] = Field(
        None, description="ANNOUNCED (tin ra) / CONFIRMED / IMPLEMENTED (thực hiện)"
    )
    scope: Optional[EventScope] = Field(
        None,
        description="MARKET (toàn thị trường) / SECTOR (ngành) / COMPANY (công ty)",
    )
    event_date: Optional[str] = Field(
        None, description="Date of the event (ISO format)"
    )
    # Crucial for Bull/Bear agents to debate
    sentiment: Optional[Sentiment] = Field(
        None, description="POSITIVE/NEGATIVE/NEUTRAL"
    )
    impact_level: Optional[ImpactLevel] = Field(None, description="HIGH/MEDIUM/LOW")
    # Traceability
    source_url: Optional[str] = Field(None, description="URL of the source article")
    extraction_date: Optional[str] = Field(None, description="ISO date when extracted")


class MacroIndicator(BaseModel):
    """
    Chỉ số Vĩ mô - Macroeconomic indicators for top-down analysis.

    Used to connect to both companies AND events.
    """

    indicator_name: str = Field(
        ..., description="e.g., 'Lãi suất liên ngân hàng', 'CPI', 'Tỷ giá USD/VND'"
    )
    trend: Optional[Trend] = Field(None, description="INCREASING/DECREASING/STABLE")
    current_status: Optional[str] = Field(
        None, description="e.g., 'Căng thẳng', 'Nới lỏng'"
    )
    affected_sectors: Optional[List[str]] = Field(
        None, description="List of industries most affected"
    )
    # Traceability
    source_url: Optional[str] = Field(None, description="URL of the source article")
    extraction_date: Optional[str] = Field(None, description="ISO date when extracted")


# =============================================================================
# EDGE TYPES (8 Relationship Types)
# =============================================================================


class CompetesWith(BaseModel):
    """Competition relationship between companies."""

    market_segment: Optional[str] = Field(
        None, description="Market segment of competition"
    )
    competition_intensity: Optional[ImpactLevel] = Field(
        None, description="HIGH/MEDIUM/LOW"
    )


class Owns(BaseModel):
    """
    Cross-ownership relationship (Sở hữu chéo).

    Use this instead of major_shareholders field for proper ontology.
    Enables queries like: "Show all companies in Vingroup ecosystem"
    """

    stake_percentage: Optional[float] = Field(
        None, description="Ownership percentage 0-100"
    )
    ownership_type: Optional[str] = Field(None, description="Direct or Indirect")
    acquisition_date: Optional[str] = Field(
        None, description="Date of acquisition (ISO format)"
    )


class Manages(BaseModel):
    """Person manages company relationship."""

    position: Optional[str] = Field(None, description="Role/position in the company")
    start_date: Optional[str] = Field(
        None, description="When they started (ISO format)"
    )
    is_current: Optional[bool] = Field(
        None, description="Whether currently in this role"
    )


class Causes(BaseModel):
    """
    STRONG causal relationship between events (Nhân quả).

    Use for clear cause-effect: "Fed rate hike" CAUSES "SBV sells USD".
    For weaker/market reaction, use Triggers instead.
    """

    causation_type: Optional[str] = Field(
        None, description="Direct, Indirect, Contributing factor"
    )
    time_lag: Optional[str] = Field(None, description="Time between cause and effect")
    confidence: Optional[float] = Field(
        None, description="Confidence in causal link 0.0-1.0"
    )


class Triggers(BaseModel):
    """
    WEAK causal relationship - market reactions, short-term effects.

    Use for: price movements, sentiment shifts, market reactions.
    Weaker than Causes, more immediate/psychological.
    """

    reaction_type: Optional[str] = Field(
        None, description="Price movement, Sentiment shift, etc."
    )
    time_lag: Optional[str] = Field(None, description="Usually immediate or very short")
    magnitude: Optional[str] = Field(None, description="Size of reaction")


class Affects(BaseModel):
    """Event affects company relationship."""

    impact_type: Optional[str] = Field(None, description="Positive, Negative, Mixed")
    impact_level: Optional[ImpactLevel] = Field(None, description="HIGH/MEDIUM/LOW")
    affected_metrics: Optional[List[str]] = Field(
        None, description="Which metrics affected"
    )


class Reported(BaseModel):
    """Company reported financial metric."""

    report_type: Optional[str] = Field(None, description="Quarterly, Annual, Flash")
    report_period: Optional[str] = Field(None, description="e.g., 'Q3/2024', 'FY2023'")


class Pressures(BaseModel):
    """Macro indicator pressures company/sector."""

    pressure_type: Optional[str] = Field(
        None, description="Cost, Demand, Regulatory pressure"
    )
    severity: Optional[ImpactLevel] = Field(None, description="HIGH/MEDIUM/LOW")


class Influences(BaseModel):
    """
    Macro indicator influences market event.

    Example: CPI tăng → NHNN thắt chặt tiền tệ
    Crucial for top-down reasoning.
    """

    influence_type: Optional[str] = Field(
        None, description="Direct policy response, Market reaction"
    )
    time_lag: Optional[str] = Field(
        None, description="Time between indicator and event"
    )


# =============================================================================
# TYPE MAPPINGS FOR GRAPHITI
# =============================================================================

# Entity types dictionary for Graphiti
ENTITY_TYPES = {
    "PublicCompany": PublicCompany,
    "FinancialMetric": FinancialMetric,
    "KeyPerson": KeyPerson,
    "MarketEvent": MarketEvent,
    "MacroIndicator": MacroIndicator,
}

# Edge types dictionary for Graphiti
EDGE_TYPES = {
    "CompetesWith": CompetesWith,
    "Owns": Owns,
    "Manages": Manages,
    "Causes": Causes,
    "Triggers": Triggers,
    "Affects": Affects,
    "Reported": Reported,
    "Pressures": Pressures,
    "Influences": Influences,
}

# Edge type mapping: which edges can exist between which entity types
EDGE_TYPE_MAP = {
    # Company-Company relationships
    ("PublicCompany", "PublicCompany"): ["CompetesWith", "Owns"],
    # Person-Company relationships
    ("KeyPerson", "PublicCompany"): ["Manages", "Owns"],
    # Event-Event relationships (CAUSAL GRAPH - the core!)
    ("MarketEvent", "MarketEvent"): ["Causes", "Triggers"],
    # Event-Company relationships
    ("MarketEvent", "PublicCompany"): ["Affects", "Triggers"],
    # Company-Metric relationships
    ("PublicCompany", "FinancialMetric"): ["Reported"],
    # Macro-Company relationships
    ("MacroIndicator", "PublicCompany"): ["Pressures"],
    # Macro-Event relationships (NEW: for top-down reasoning)
    ("MacroIndicator", "MarketEvent"): ["Influences", "Causes"],
    # Fallback for any other relationships
    ("Entity", "Entity"): ["Causes", "Affects", "Triggers"],
}
