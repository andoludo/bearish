from dotenv import load_dotenv
import logging.config


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: [%(funcName)s] %(message)s"
        },
    },
    "handlers": {
        "console": {
            "level": "ERROR",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "formatter": "standard",
            "filename": "bearish.log",
            "mode": "w+",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}


logging.config.dictConfig(LOGGING_CONFIG)
load_dotenv()
