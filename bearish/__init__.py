"""Bearish: fetch, normalise, and persist financial data for offline analysis."""
from bearish.exceptions import BearishError, RepositoryError, SourceError
from bearish.models import Asset, AssetKind, FinancialStatement, Period, Price
from bearish.repository import SqliteRepository
from bearish.service import BearishService
from bearish.sources.base import FinancialDataSource
from bearish.sources.memory import InMemorySource

__all__ = [
    "Asset",
    "AssetKind",
    "BearishError",
    "BearishService",
    "FinancialDataSource",
    "FinancialStatement",
    "InMemorySource",
    "Period",
    "Price",
    "RepositoryError",
    "SourceError",
    "SqliteRepository",
]

__version__ = "0.50.0"
