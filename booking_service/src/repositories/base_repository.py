from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, obj_id: Any) -> ModelType | None:
        return await self.session.get(self.model, obj_id)

    def add(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        return obj
