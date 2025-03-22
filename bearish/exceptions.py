class InvalidApiKeyError(Exception):
    pass


class LimitApiKeyReachedError(Exception):
    pass


class TickerNotFoundError(Exception):
    pass
