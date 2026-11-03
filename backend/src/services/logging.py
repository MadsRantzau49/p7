import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


class Logging:
    @property
    def logger(self) -> logging.Logger:
        """Normal log function"""
        return logging.getLogger(type(self).__name__)

    @contextmanager
    def log_step(self, name: str) -> Iterator[None]:
        """Log execution time and errors for an algorithm step."""
        self.logger.info("Starting %s", name)
        start = perf_counter()

        try:
            yield
        except Exception:
            self.logger.exception(
                "%s failed after %.3f seconds",
                name,
                perf_counter() - start,
            )
            raise
        else:
            self.logger.info(
                "%s completed in %.3f seconds",
                name,
                perf_counter() - start,
            )
