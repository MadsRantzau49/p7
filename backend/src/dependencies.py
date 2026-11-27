from typing import Annotated

from database.connection import create_db_connection, database_pool
from database.database_actions import DatabaseActions
from database.repositories.dataset_repository import DatasetRepository
from database.repositories.health_repository import HealthRepository
from database.repositories.trajectory_repository import TrajectoryRepository
from fastapi import Depends
from psycopg import Connection
from services.cleaning_service import CleanService
from services.clustering_service import ClusteringService
from services.health_service import HealthService
from services.subtrajectory_service import SubtrajectoryService


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


def get_route_clustering_service() -> ClusteringService:
    """Provides a route clustering service"""
    return ClusteringService()


def get_health_repository() -> HealthRepository:
    """Provides a health repository that borrows its own connection with a short timeout"""
    return HealthRepository(pool=database_pool)


def get_health_service(
    health_repository: Annotated[HealthRepository, Depends(get_health_repository)],
) -> HealthService:
    """Provides a health service"""
    return HealthService(health_repository=health_repository)
