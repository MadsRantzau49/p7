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


def get_db_connection():
    """Creates the connection needed for different components.
    Documentation: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#sub-dependencies-with-yield
    """
    connection = create_db_connection()
    try:
        yield connection
    finally:
        connection.close()


def get_trajectory_repository(connection: PooledMySQLConnection):
    """Create a trajectory repository using provided connection"""
    return TrajectoryRepository(connection)


def get_dataset_repository(connection: PooledMySQLConnection):
    """Create a dataset repository using provided connection"""
    return DatasetRepository(connection)


def get_database_actions(connection: PooledMySQLConnection):
    """Create a database actions using provided connection"""
    return DatabaseActions(connection)


def get_import_repository(connection: PooledMySQLConnection):
    """Create a import repository using provided connection"""
    return ImportRepository(connection)


def get_trajectory_service():
    """Provides a trajectory service and close its connection afterward."""
    connection = create_db_connection()
    try:
        yield TrajectoryService(
            trajectory_repository=get_trajectory_repository(connection),
            dataset_repository=get_dataset_repository(connection),
            db_actions=get_database_actions(connection),
        )
    finally:
        connection.close()


def get_dataset_upload_service():
    """Provides a dataset upload service and close loses the connection after use"""
    connection = create_db_connection()
    try:
        yield UploadDataset(
            database_actions=get_database_actions(connection),
            trajectory_repository=get_trajectory_repository(connection),
            dataset_repository=get_dataset_repository(connection),
        )
    finally:
        connection.close()


def get_cleaning_service():
    """Provides a cleaning service and close loses the connection after use"""
    connection = create_db_connection()
    try:
        yield CleanService(
            trajectory_repository=get_trajectory_repository(connection),
            db_actions=get_database_actions(connection),
        )
    finally:
        connection.close()


def get_subpath_service():
    """Provides a subpath service and close loses the connection after use"""
    connection = create_db_connection()
    try:
        yield SubPathService(trajectory_repository=get_trajectory_repository(connection))
    finally:
        connection.close()
