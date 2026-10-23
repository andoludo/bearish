"""Macro-economic, commodity and market-regime data.

Unlike the ticker-centric ``bearish.sources`` package, everything here is
keyed by *concept* (``CPI_YOY``, ``POLICY_RATE``, ...) and *entity* (an ISO-3
country, a commodity code, a region) so that series from different providers
are directly comparable. Observations are stored point-in-time: each value
carries the ``as_of`` date on which it became known.
"""
