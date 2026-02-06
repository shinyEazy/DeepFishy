"""Crawler package for web crawling and data extraction."""

from .spiders import (
    BaseSpider,
    ArticleURLSpider,
    ArticleContentSpider,
)
from .pipeline import CrawlerPipeline

__all__ = [
    "BaseSpider",
    "ArticleURLSpider",
    "ArticleContentSpider",
    "CrawlerPipeline",
]
