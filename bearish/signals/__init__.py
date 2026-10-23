"""Event and per-ticker signal data.

Complements the concept-keyed macro store with two shapes it cannot hold:

* dated **events** (elections, FOMC meetings, conflict onsets, sanctions
  waves) that event studies are anchored on, and their measured returns;
* point-in-time **ticker signals** (theme mentions in filings, short interest,
  federal awards, lobbying spend, ...) keyed by symbol rather than by country.

Discrete records with their own identity — congressional trades and
prediction-market quotes — get dedicated tables.
"""
