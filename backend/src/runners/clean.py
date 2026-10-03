import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from services.cleaning_service import clean_dataset

CITIES = ("Beijing",)
BATCH_SIZE = 1000

if __name__ == "__main__":
    for city in CITIES:
        print(f"cleaning city {city}")
        report = clean_dataset(city, batch_size=BATCH_SIZE)
        print(report)
