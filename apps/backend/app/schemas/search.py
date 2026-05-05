from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID


class SearchQuery(BaseModel):
    query: str
    limit: int = 10
    category: Optional[str] = None


class SearchResult(BaseModel):
    id: UUID
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    type: str
    tags: List[str] = []
    similarity_score: float
    created_at: str
