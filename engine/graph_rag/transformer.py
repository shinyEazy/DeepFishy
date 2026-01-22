"""Graph transformer using LangChain's LLMGraphTransformer."""

from typing import List, Optional, Dict, Any
from collections import Counter

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer

from app.core.logging import logger
from app.services.neo4j import get_neo4j_service
from app.engine.graph_rag.models import ExtractionConfig, GraphBuildResult


class GraphRAGTransformer:
    """
    Wrapper around LangChain's LLMGraphTransformer.

    Provides:
    - LLMGraphTransformer configuration for financial domain
    - Neo4j ingestion with automatic indexing
    - Temporal property extraction hints
    - Statistics tracking

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> llm = ChatOpenAI(model="gpt-4o-mini")
        >>> transformer = GraphRAGTransformer(llm=llm)
        >>> result = transformer.extract_and_store([doc1, doc2])
        >>> print(f"Created {result.nodes_created} nodes")
    """

    def __init__(
        self,
        llm,
        config: Optional[ExtractionConfig] = None,
    ):
        """
        Initialize the graph transformer.

        Args:
            llm: LangChain chat model for extraction
            config: Optional extraction configuration
        """
        self.llm = llm
        self.config = config or ExtractionConfig()
        self._neo4j_service = None

        # Initialize LangChain's LLMGraphTransformer
        self.transformer = LLMGraphTransformer(
            llm=llm,
            allowed_nodes=self.config.allowed_nodes,
            allowed_relationships=self.config.allowed_relationships,
            node_properties=self.config.include_properties,
            relationship_properties=True,  # Enable temporal properties
        )

        logger.info(
            f"GraphRAGTransformer initialized with "
            f"{len(self.config.allowed_nodes)} node types, "
            f"{len(self.config.allowed_relationships)} relationship types"
        )

    @property
    def neo4j_service(self):
        """Lazy load Neo4j service."""
        if self._neo4j_service is None:
            self._neo4j_service = get_neo4j_service()
        return self._neo4j_service

    def extract(self, documents: List[Document]) -> List:
        """
        Extract graph documents without storing.

        Args:
            documents: List of LangChain Documents to process

        Returns:
            List of GraphDocument objects
        """
        logger.info(f"Extracting graph from {len(documents)} documents")

        try:
            graph_documents = self.transformer.convert_to_graph_documents(documents)

            nodes_count = sum(len(gd.nodes) for gd in graph_documents)
            rels_count = sum(len(gd.relationships) for gd in graph_documents)

            logger.info(f"Extracted {nodes_count} nodes, {rels_count} relationships")

            return graph_documents

        except Exception as e:
            logger.error(f"Graph extraction failed: {e}", exc_info=True)
            raise

    def extract_and_store(
        self,
        documents: List[Document],
    ) -> GraphBuildResult:
        """
        Extract graph from documents and store in Neo4j.

        Args:
            documents: List of LangChain Documents to process

        Returns:
            GraphBuildResult with statistics
        """
        logger.info(f"Extracting and storing graph from {len(documents)} documents")

        errors = []
        node_types_counter = Counter()
        rel_types_counter = Counter()

        try:
            # Extract graph documents using LLMGraphTransformer
            graph_documents = self.transformer.convert_to_graph_documents(documents)

            # Count node and relationship types
            for gd in graph_documents:
                for node in gd.nodes:
                    node_types_counter[node.type] += 1
                for rel in gd.relationships:
                    rel_types_counter[rel.type] += 1

            # Store in Neo4j using LangChain's built-in method
            self.neo4j_service.graph.add_graph_documents(
                graph_documents,
                baseEntityLabel=True,
                include_source=self.config.include_source,
            )

            # Calculate totals
            nodes_count = sum(len(gd.nodes) for gd in graph_documents)
            rels_count = sum(len(gd.relationships) for gd in graph_documents)

            logger.info(
                f"Stored {nodes_count} nodes, {rels_count} relationships in Neo4j"
            )

            return GraphBuildResult(
                nodes_created=nodes_count,
                relationships_created=rels_count,
                source_documents=len(documents),
                node_types=dict(node_types_counter),
                relationship_types=dict(rel_types_counter),
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Graph extraction and storage failed: {e}", exc_info=True)
            errors.append(str(e))
            return GraphBuildResult(
                nodes_created=0,
                relationships_created=0,
                source_documents=len(documents),
                errors=errors,
            )

    def create_temporal_indices(self) -> None:
        """Create indices for efficient temporal queries."""
        logger.info("Creating temporal indices in Neo4j")
        self.neo4j_service.create_indices()

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        return self.neo4j_service.get_stats()


def get_graph_transformer(llm=None, config: Optional[ExtractionConfig] = None):
    """
    Factory function to create a GraphRAGTransformer.

    Args:
        llm: Optional LLM (will be created from environment if not provided)
        config: Optional extraction configuration

    Returns:
        GraphRAGTransformer instance
    """
    if llm is None:
        # Lazy import to avoid circular dependencies
        from app.services.llm_provider import get_llm

        llm = get_llm()

    return GraphRAGTransformer(llm=llm, config=config)
