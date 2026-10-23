"""Populate the tables that connect macro entities to assets.

* ``countryref`` / ``countryalias`` so ``equity.country`` spellings resolve to
  ISO-3 through the ``equitycountry`` view,
* ``sectoralias`` so ``equity.sector`` / ``equity.industry`` spellings resolve
  to GICS names through the ``equitysector`` view,
* ``sectorcommoditysensitivity`` (curated priors),
* ``etfexposure`` derived from stored ETF metadata.
"""

import logging
from typing import Dict

from bearish.interface.interface import BearishDbBase
from bearish.macro.etf_exposure import write_etf_exposures
from bearish.macro.links import country_references
from bearish.macro.sectors import sector_aliases
from bearish.macro.sensitivities import write_sector_sensitivities

logger = logging.getLogger(__name__)


def write_country_references(db: BearishDbBase) -> int:
    refs, aliases = country_references()
    db.write_country_references(refs, aliases)
    return len(refs)


def write_sector_references(db: BearishDbBase) -> int:
    aliases = sector_aliases()
    db.write_sector_aliases(aliases)
    return len(aliases)


def run_linking(db: BearishDbBase) -> Dict[str, int]:
    """Write every linking table; returns row counts per table."""
    counts = {
        "countryref": write_country_references(db),
        "sectoralias": write_sector_references(db),
        "sectorcommoditysensitivity": write_sector_sensitivities(db),
        "etfexposure": write_etf_exposures(db),
    }
    logger.info(f"Linking tables written: {counts}")
    return counts
