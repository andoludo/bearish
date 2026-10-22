import abc
import datetime
import logging
import time
from typing import Any, ClassVar, Dict, List, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field, validate_call
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bearish.exceptions import InvalidApiKeyError
from bearish.macro.models import MacroSeries, MacroSources, Observation
from bearish.sources.base import ApiUsage, check_api_limit
from bearish.utils.utils import observability

logger = logging.getLogger(__name__)

# Several providers (SEC, FRED, OECD) reject anonymous or generic agents.
USER_AGENT = "bearish (https://github.com/andoludo/bearish)"


class AbstractMacroSource(BaseModel, abc.ABC):
    """A provider of catalog series.

    Subclasses implement ``_read_observations`` for the catalog entries whose
    ``source`` matches ``__source__``; the public ``read_observations`` adds
    filtering, API-usage accounting and error isolation, mirroring
    ``bearish.sources.base.AbstractSource``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    __source__: ClassVar[MacroSources]
    __api_key__: ClassVar[Optional[str]] = None
    requires_api_key: ClassVar[bool] = False

    api_usage: ApiUsage = Field(default_factory=ApiUsage)
    pause: float = Field(default=1.0, description="Seconds to wait between HTTP calls")
    timeout: int = 60

    def set_api_key(self, api_key: Optional[str]) -> None:
        if self.requires_api_key and not api_key:
            raise InvalidApiKeyError(f"{self.__source__} requires an API key ({self.__source__.upper()}_API_KEY)")
        type(self).__api_key__ = api_key

    def set_pause(self, pause: float) -> None:
        self.pause = pause

    def owns(self, series: MacroSeries) -> bool:
        return series.source == self.__source__

    @validate_call(validate_return=True)
    @check_api_limit
    @observability
    def read_observations(self, series: List[MacroSeries], start: Optional[datetime.date] = None) -> List[Observation]:
        own = [s for s in series if self.owns(s)]
        if not own:
            return []
        logger.debug(f"Reading {len(own)} series from {type(self).__name__}")
        try:
            return self._read_observations(own, start)
        except Exception as e:
            logger.error(f"Error reading observations from {type(self).__name__}: {e}", exc_info=True)
            return []

    @abc.abstractmethod
    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]: ...

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """One polite GET: shared User-Agent, timeout, pause and call accounting."""
        if self.api_usage.calls:
            time.sleep(self.pause)
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            timeout=self.timeout,
        )
        self.api_usage.add_api_calls(1)
        response.raise_for_status()
        return response

    @staticmethod
    def today() -> datetime.date:
        return datetime.date.today()
