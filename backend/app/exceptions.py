class AppError(Exception):
    pass


class DatabaseError(AppError):
    pass


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(f"{resource} not found: {resource_id}")
        self.resource = resource
        self.resource_id = resource_id


class IngestionError(AppError):
    pass


class EmbeddingError(AppError):
    pass


class RetrievalError(AppError):
    pass


class ChatError(AppError):
    pass
