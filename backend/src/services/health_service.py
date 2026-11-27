from database.repositories.health_repository import HealthRepository

class HealthService:
    def __init__(self, health_repository: HealthRepository) -> None:
        self.health_repository = health_repository
        
    def check_health(self) -> dict[str, str]:
        """Check if the service is running and the database connection is healthy."""
        if self.health_repository.ping():
            return {
                "status": "healthy",
                "Database connection": "connected"
            }
        else:
            return {
                "status": "unhealthy",
                "Database connection": "disconnected"
            }
