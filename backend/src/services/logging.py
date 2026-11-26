import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from time import perf_counter


def log_heading(logger: logging.Logger, name: str) -> None:
    """Mark the start of a request or service."""
    logger.info("=== %s ===", name)


@contextmanager
def log_step(logger: logging.Logger, name: str) -> Iterator[None]:
    """Log a single timing line when a step finishes, or log its failure."""
    start = perf_counter()
    try:
        yield
    except Exception:
        logger.exception("%s failed after %.3f seconds", name, perf_counter() - start)
        raise
    else:
        logger.info("%s took %.3f seconds", name, perf_counter() - start)


class Logging:
    @property
    def logger(self) -> logging.Logger:
        """Normal log function"""
        return logging.getLogger(type(self).__name__)

    def log_heading(self) -> None:
        """Mark the start of this service."""
        log_heading(self.logger, type(self).__name__)

    def log_step(self, name: str) -> AbstractContextManager[None]:
        """Time a step using this service's logger."""
        return log_step(self.logger, name)
