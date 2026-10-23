"""Technology-adoption catalog: arXiv papers and SEC filings per theme."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries
from bearish.signals.sources.edgar_themes import theme_filings_series
from bearish.signals.themes import THEMES

SERIES: List[MacroSeries] = [
    *[
        series(
            "ADOPTION_PAPERS",
            theme.key.upper(),
            "arXiv",
            f"arxiv:{theme.key}",
            "M",
            entity_type="theme",
            description=f"arXiv papers per month mentioning: {theme.label}",
        )
        for theme in THEMES.values()
        if theme.arxiv_phrases
    ],
    *[theme_filings_series(theme) for theme in THEMES.values()],
]
