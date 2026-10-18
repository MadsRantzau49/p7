from database.connection import create_db_connection
from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.import_repository import ImportRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from mysql.connector.pooling import PooledMySQLConnection
from services.cleaning_service import CleanService
from services.dataset_upload_service import UploadDataset
from services.subpath_service import SubPathService
from services.trajectory_service import TrajectoryService
from fastapi import Depends
from typing import Annotated


def get_db_connection():
    """Creates the connection needed for different components.
    Documentation: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#sub-dependencies-with-yield
    """
    connection = create_db_connection()
    try:
        yield connection
    finally:
        connection.close()


def get_trajectory_repository(connection: Annotated[PooledMySQLConnection, Depends(get_db_connection)]):
    """Create a trajectory repository using provided connection"""
    return TrajectoryRepository(connection)


def get_dataset_repository(connection: Annotated[PooledMySQLConnection, Depends(get_db_connection)]):
    """Create a dataset repository using provided connection"""
    return DatasetRepository(connection)


def get_database_actions(connection: Annotated[PooledMySQLConnection, Depends(get_db_connection)]):
    """Create a database actions using provided connection"""
    return DatabaseActions(connection)


def get_import_repository(connection: Annotated[PooledMySQLConnection, Depends(get_db_connection)]):
    """Create a import repository using provided connection"""
    return ImportRepository(connection)


def get_trajectory_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
    dataset_repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
    db_actions: Annotated[DatabaseActions, Depends(get_database_actions)],
) -> TrajectoryService:
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
    return UploadDataset(
        database_actions=database_actions,
        trajectory_repository=trajectory_repository,
        dataset_repository=dataset_repository,
    )


def get_cleaning_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
    db_actions: Annotated[DatabaseActions, Depends(get_database_actions)],
) -> CleanService:
    return CleanService(
        trajectory_repository=trajectory_repository,
        db_actions=db_actions,
    )


def get_subpath_service(
    trajectory_repository: Annotated[TrajectoryRepository, Depends(get_trajectory_repository)],
) -> SubPathService:
    return SubPathService(
        trajectory_repository=trajectory_repository,
    )
