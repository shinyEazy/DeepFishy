"""Compatibility shim for the Neo4j service."""

from deepfishy.infra.graph.neo4j import Neo4jService, get_neo4j_service

__all__ = ["Neo4jService", "get_neo4j_service"]
