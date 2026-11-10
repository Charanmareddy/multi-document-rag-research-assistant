"""Central logging configuration."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure consistent console logging for local deployment."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
