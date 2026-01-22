"""Models for Graph RAG extraction and storage."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class NodeType(str, Enum):
    """Allowed node types for extraction."""

    ORGANIZATION = "Organization"
    PERSON = "Person"
    EVENT = "Event"
    POLICY = "Policy"
    MARKET_INDEX = "MarketIndex"
    CURRENCY = "Currency"
    COMMODITY = "Commodity"
    COMPANY = "Company"
    COUNTRY = "Country"
    SECTOR = "Sector"


class RelationshipType(str, Enum):
    """Allowed relationship types for extraction."""

    CAUSES = "CAUSES"
    AFFECTS = "AFFECTS"
    LEADS_TO = "LEADS_TO"
    PREDICTS = "PREDICTS"
    CORRELATES_WITH = "CORRELATES_WITH"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    LOCATED_IN = "LOCATED_IN"
    WORKS_FOR = "WORKS_FOR"
    ANNOUNCES = "ANNOUNCES"


class ExtractionConfig(BaseModel):
    """Configuration for graph extraction."""

    allowed_nodes: List[str] = Field(
        default=[nt.value for nt in NodeType], description="List of allowed node types"
    )
    allowed_relationships: List[str] = Field(
        default=[rt.value for rt in RelationshipType],
        description="List of allowed relationship types",
    )
    include_properties: bool = Field(
        default=True, description="Whether to extract node properties"
    )
    include_source: bool = Field(
        default=True, description="Whether to link nodes to source documents"
    )

    class Config:
        use_enum_values = True


class GraphBuildResult(BaseModel):
    """Result of graph building operation."""

    nodes_created: int = Field(description="Number of nodes created")
    relationships_created: int = Field(description="Number of relationships created")
    source_documents: int = Field(description="Number of source documents processed")
    node_types: Dict[str, int] = Field(
        default_factory=dict, description="Count by node type"
    )
    relationship_types: Dict[str, int] = Field(
        default_factory=dict, description="Count by relationship type"
    )
    errors: List[str] = Field(
        default_factory=list, description="Any errors during extraction"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the extraction was performed"
    )


class GraphQueryResult(BaseModel):
    """Result of knowledge graph query."""

    nodes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Matched nodes"
    )
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, description="Matched relationships"
    )
    paths: List[Dict[str, Any]] = Field(
        default_factory=list, description="Matched paths (for chain queries)"
    )
    query_time_ms: float = Field(description="Query execution time in milliseconds")
    context_text: str = Field(description="Formatted text for LLM consumption")
    total_results: int = Field(default=0, description="Total number of results")


class TemporalFilter(BaseModel):
    """Filter for temporal queries."""

    time_period: Optional[str] = Field(
        default=None, description="Time period filter (e.g., 'Q3/2025', '10/2025')"
    )
    start_date: Optional[datetime] = Field(
        default=None, description="Start date for range queries"
    )
    end_date: Optional[datetime] = Field(
        default=None, description="End date for range queries"
    )

    def to_cypher_condition(self, node_alias: str = "n") -> str:
        """Convert filter to Cypher WHERE condition."""
        conditions = []

        if self.time_period:
            conditions.append(f"{node_alias}.time_period CONTAINS $time_period")

        if self.start_date:
            conditions.append(f"{node_alias}.timestamp >= datetime($start_date)")

        if self.end_date:
            conditions.append(f"{node_alias}.timestamp <= datetime($end_date)")

        return " AND ".join(conditions) if conditions else "1=1"
