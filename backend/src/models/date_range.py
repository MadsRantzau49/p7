from dataclasses import dataclass
from datetime import date


@dataclass
class DateRange:
    start_date: date | None = None
    end_date: date | None = None

    def validate(self) -> None:
        """Reject a range whose start is later than its end."""
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")

    def contains(self, departure_date: date) -> bool:
        """Check whether a local departure date is inside the inclusive range."""
        return (self.start_date is None or departure_date >= self.start_date) and (
            self.end_date is None or departure_date <= self.end_date
        )
