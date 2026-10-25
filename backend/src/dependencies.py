from typing import Annotated

from database.connection import create_db_connection
from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from fastapi import Depends
from psycopg import Connection
from services.cleaning_service import CleanService
from services.dataset_upload_service import UploadDataset
from services.subtrajectory_service import SubtrajectoryService
from services.trajectory_service import TrajectoryService


def get_db_connection():
    """Creates the connection needed for different components.
    Documentation: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#sub-dependencies-with-yield
    """
    with create_db_connection() as connection:
        yield connection


def get_trajectory_repository(connection: Annotated[Connection, Depends(get_db_connection)]):
    """Create a trajectory repository using provided connection"""
    return TrajectoryRepository(connection)


def get_dataset_repository(connection: Annotated[Connection, Depends(get_db_connection)]):
    """Create a dataset repository using provided connection"""
    return DatasetRepository(connection)


def get_database_actions(connection: Annotated[Connection, Depends(get_db_connection)]):
    """Create a database actions using provided connection"""
    return DatabaseActions(connection)


def get_import_repository(connection: Annotated[Connection, Depends(get_db_connection)]):
    """Create a import repository using provided connection"""
    return ImportRepository(connection)


def get_trajectory_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
    dataset_repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
    db_actions: Annotated[DatabaseActions, Depends(get_database_actions)],
) -> TrajectoryService:
    """Provides a trajectory service and closes the connection afterward"""
    return TrajectoryService(
        trajectory_repository=trajectory_repository,
        dataset_repository=dataset_repository,
        db_actions=db_actions,
    )


def get_dataset_upload_service(
    database_actions: Annotated[DatabaseActions, Depends(get_database_actions)],
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
    dataset_repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
) -> UploadDataset:
    """Provides a dataset upload service and closes the connection afterward"""
    return UploadDataset(
        database_actions=database_actions,
        trajectory_repository=trajectory_repository,
        dataset_repository=dataset_repository,
    )


def get_cleaning_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
    db_actions: Annotated[DatabaseActions, Depends(get_database_actions)],
) -> CleanService:
    """Provides a cleaning service and closes the connection afterward"""
    return CleanService(
        trajectory_repository=trajectory_repository,
        db_actions=db_actions,
    )


def get_subtrajectory_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
) -> SubtrajectoryService:
    """Provides a subtrajectory service and closes the connection afterward"""
    return SubtrajectoryService(
        trajectory_repository=trajectory_repository,
    )
