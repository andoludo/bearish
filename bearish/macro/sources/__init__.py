"""Provider implementations for the macro catalog."""

from typing import List

from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.bis import BisSource
from bearish.macro.sources.cftc import CftcSource
from bearish.macro.sources.dbnomics import DbnomicsSource
from bearish.macro.sources.ecb import EcbSource
from bearish.macro.sources.epu import EpuSource
from bearish.macro.sources.eurostat import EurostatSource
from bearish.macro.sources.fred import FredSource
from bearish.macro.sources.gdpnow import GdpNowSource
from bearish.macro.sources.gpr import GprSource
from bearish.macro.sources.imf import ImfSource
from bearish.macro.sources.kenfrench import KenFrenchSource
from bearish.macro.sources.oecd import OecdSource
from bearish.macro.sources.pinksheet import PinkSheetSource
from bearish.macro.sources.portwatch import PortWatchSource
from bearish.macro.sources.sipri import SipriSource
from bearish.macro.sources.worldbank import WorldBankSource

__all__ = [
    "AbstractMacroSource",
    "BisSource",
    "CftcSource",
    "DbnomicsSource",
    "EcbSource",
    "EpuSource",
    "EurostatSource",
    "FredSource",
    "GdpNowSource",
    "GprSource",
    "ImfSource",
    "KenFrenchSource",
    "OecdSource",
    "PinkSheetSource",
    "PortWatchSource",
    "SipriSource",
    "WorldBankSource",
    "default_macro_sources",
]


def default_macro_sources() -> List[AbstractMacroSource]:
    """Providers fetched by ``bearish macro`` / ``bearish update``; cheap keyless APIs first, bulk files last.

    GDELT (one ~8 MB file per day) and OFAC (a ~110 MB list) are heavy and are
    fetched by ``bearish conflicts`` instead.
    """
    return [
        FredSource(),
        OecdSource(),
        EurostatSource(),
        EcbSource(),
        BisSource(),
        ImfSource(),
        WorldBankSource(),
        DbnomicsSource(),
        CftcSource(),
        KenFrenchSource(),
        PinkSheetSource(),
        EpuSource(),
        GprSource(),
        GdpNowSource(),
        PortWatchSource(),
        SipriSource(),
    ]
