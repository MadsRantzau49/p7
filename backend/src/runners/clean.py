import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dependencies import (
    get_cleaning_service,
    get_database_actions,
    get_db_connection,
    get_trajectory_repository,
)

CITIES = ("Beijing",)
BATCH_SIZE = 1000

if __name__ == "__main__":
    for city in CITIES:
        print(f"cleaning city {city}")

        with contextmanager(get_db_connection)() as connection:
            service = get_cleaning_service(
                get_trajectory_repository(connection),
                get_database_actions(connection),
            )
            report = service.clean_dataset(city, batch_size=BATCH_SIZE)
            print(report)
