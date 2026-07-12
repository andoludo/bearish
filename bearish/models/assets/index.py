from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.assets.base import BaseComponent
from bearish.models.base import Ticker
from bearish.utils.utils import to_string

PRICE_INDEX = [
    Ticker(symbol="^GSPC"),  # S&P 500
    Ticker(symbol="^DJI"),  # Dow Jones Industrial Average
    Ticker(symbol="^IXIC"),  # Nasdaq Composite
    Ticker(symbol="^RUT"),  # Russell 2000
    Ticker(symbol="SPG1200"),  # S&P Global 1200 (varies by feed)
    Ticker(symbol="URTH"),  # MSCI World (ETF proxy)
    Ticker(symbol="IOO"),  # S&P Global 100 (ETF proxy)
    Ticker(symbol="SPBMISR"),  # S&P Global BMI (varies)
    Ticker(symbol="^FTSE"),  # FTSE 100
    Ticker(symbol="MCX"),  # FTSE 250 (LSE)
    Ticker(symbol="^FCHI"),  # CAC 40
    Ticker(symbol="^GDAXI"),  # DAX
    Ticker(symbol="^N225"),  # Nikkei 225
    Ticker(symbol="^TOPX"),  # TOPIX (provider dependent)
    Ticker(symbol="^HSI"),  # Hang Seng
    Ticker(symbol="000001.SS"),  # Shanghai Composite
    Ticker(symbol="^AXJO"),  # S&P/ASX 200
    Ticker(symbol="^GSPTSE"),  # TSX Composite
    Ticker(symbol="^BSESN"),  # BSE Sensex
    Ticker(symbol="^NSEI"),  # Nifty 50
    Ticker(symbol="^KS11"),  # KOSPI
    Ticker(symbol="^SET.BK"),  # SET Thailand
    Ticker(symbol="^BVSP"),  # Ibovespa
    Ticker(symbol="^TX60"),  # S&P/TSX 60 (varies)
    Ticker(symbol="FTSEMIB.MI"),  # FTSE MIB
    Ticker(symbol="^SSMI"),  # Swiss Market Index
    Ticker(symbol="^STOXX50E"),  # Euro Stoxx 50
    Ticker(symbol="^STOXX"),  # Stoxx Europe 600
    Ticker(symbol="EEM"),  # MSCI Emerging Markets (ETF proxy)
    Ticker(symbol="ACWI"),  # MSCI ACWI (ETF proxy)
    Ticker(symbol="^SPTSE"),  # S&P/TSX Composite
    Ticker(symbol="^AXKO"),  # S&P/ASX 50 (varies)
    Ticker(symbol="ILF"),  # S&P Latin America 40 (ETF proxy)
    Ticker(symbol="AIA"),  # S&P Asia 50 (ETF proxy)
    Ticker(symbol="TPX100"),  # S&P/TOPIX 150 (varies)
    Ticker(symbol="^DJGT50"),  # DJ Global Titans 50 (varies)
    Ticker(symbol="SP1500"),  # S&P Composite 1500 (varies)
    Ticker(symbol="^RUA"),  # Russell 3000
    Ticker(symbol="399001.SZ"),  # SZSE Component
    Ticker(symbol="000300.SS"),  # CSI 300
    Ticker(symbol="^FTAS"),  # FTSE All-Share
    Ticker(symbol="IEUR"),  # MSCI Europe (ETF proxy)
    Ticker(symbol="IPAC"),  # MSCI Asia Pacific (ETF proxy)
    Ticker(symbol="FM"),  # MSCI Frontier Markets (ETF proxy)
    Ticker(symbol="^MXX"),  # S&P/BMV IPC Mexico
    Ticker(symbol="^AEX"),  # AEX
    Ticker(symbol="^OMXC20"),  # OMX Copenhagen 20
    Ticker(symbol="^BFX"),  # BEL 20
    Ticker(symbol="XU100.IS"),  # BIST 100 Turkey
    Ticker(symbol="PSEI.PS"),  # PSEi Philippines
    Ticker(symbol="0020.Z"),  # PSEi Philippines
]


class Index(BaseComponent):
    category_group: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]
    category: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None),
    ]
