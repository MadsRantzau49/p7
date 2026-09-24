import os
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import database.queries
from database.connection import create_db_connection
from dotenv import load_dotenv
from helpers.parsers import parse_beijing_trajectories, parse_porto_trajectories
from helpers.trajectory_helpers import (
    convert_beijing_trajectory,
    convert_porto_trajectory,
)

load_dotenv()


def save_porto_trajectories(dataset_name: str, batch_size: int) -> None:
    """Save Porto trajectories to the database in batches."""
    context = create_db_connection()

    try:
        dataset_id = database.queries.get_dataset_id(context, dataset_name)

        trajectories = parse_porto_trajectories(os.getenv("PORTO_DATASET_PATH"))

        total = len(trajectories)

        for start in range(0, total, batch_size):
            print("Batch started")
            batch = trajectories[start : start + batch_size]

            # Generate source IDs ourselves
            for trajectory in batch:
                trajectory.source_id = str(uuid.uuid4())

            source_ids = []

            for trajectory in batch:
                source_ids.append(trajectory.source_id)

            # Creates bridge entry
            database.queries.create_source_trajectories(context, dataset_id, source_ids)

            # Inserts trajectory data, with source_id from source_trajectories table as PR and FK
            database.queries.insert_porto_trajectories(context, batch)

            context.commit()
            print("Batch ended")

    except Exception as error:
        context.rollback()
        print(f"Failed to save trajectories: {error}")
        raise

    finally:
        context.close()


def save_dataset_trajectories(dataset_name: str, batch_size) -> None:
    """Save trajectory data to the database in batches."""
    context = create_db_connection()
    source_ids = []
    try:
        dataset_id = database.queries.get_dataset_id(context, dataset_name)

        trajectories = parse_beijing_trajectories(os.getenv("BEIJING_DATASET_PATH"))

        total = len(trajectories)

        for start in range(0, total, batch_size):
            print("batch started")
            batch = trajectories[start : start + batch_size]

            for trajectory in batch:
                trajectory.source_id = str(uuid.uuid4())

            source_ids = []

            for trajectory in batch:
                source_ids.append(trajectory.source_id)

            database.queries.create_source_trajectories(context, dataset_id, source_ids)

            database.queries.insert_beijing_dataset(context, batch)

            context.commit()
            print("Batch ended")

    except Exception as error:
        context.rollback()
        print(f"Failed to save beijing trajectories: {error}")
        raise

    finally:
        context.close()


def create_uniformed_data_structure(batch_size: int):
    """Convert Porto and Beijing data into the uniform trajectory format."""
    context = create_db_connection()

    porto_total = 0
    beijing_total = 0

    try:
        # Porto
        last_source_id = None

        while True:
            porto_data = database.queries.retrieve_porto_dataset_batch(context, batch_size, last_source_id)

            if not porto_data:
                break

            uniformed_trajectories = []

            for data in porto_data:
                uniformed_trajectories.append(convert_porto_trajectory(data))

            database.queries.insert_data_uniformed_trajectories(context, uniformed_trajectories)

            context.commit()

            porto_total += len(uniformed_trajectories)
            last_source_id = porto_data[-1]["source_id"]

            print(f"Created {porto_total} trajectories from Porto")

        last_source_id = None

        # Beijing
        while True:
            beijing_data = database.queries.retrieve_beijing_data_batch(context, batch_size, last_source_id)

            if not beijing_data:
                break

            uniformed_trajectories = []

            for data in beijing_data:
                uniformed_trajectories.append(convert_beijing_trajectory(data))

            database.queries.insert_data_uniformed_trajectories(context, uniformed_trajectories)

            context.commit()

            beijing_total += len(uniformed_trajectories)
            last_source_id = beijing_data[-1]["source_id"]

            print(f"Created {beijing_total} trajectories from Beijing")

        total_created = porto_total + beijing_total

        print(f"Created {total_created} trajectories in total")

        return total_created

    except Exception as error:
        context.rollback()
        print(f"Failed to create uniformed data structure: {error}")
        raise

    finally:
        context.close()
