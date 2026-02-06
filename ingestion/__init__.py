"""Ingestion package for data pipeline operations."""

from .crawler import (
    BaseSpider,
    ArticleURLSpider,
    ArticleContentSpider,
    CrawlerPipeline,
)

__all__ = [
    "BaseSpider",
    "ArticleURLSpider",
    "ArticleContentSpider",
    "CrawlerPipeline",
]
