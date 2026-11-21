from dataclasses import dataclass
from datetime import date


@dataclass
class DateRange:
    start_date: date
    end_date: date

    def validate(self) -> None:
        """Reject a range whose start is later than its end."""
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")

    def contains(self, departure_date: date) -> bool:
        """Check whether a local departure date is inside the inclusive range."""
        return self.start_date <= departure_date <= self.end_date
