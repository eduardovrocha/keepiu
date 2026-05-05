from typing import List, Dict
from pydantic import BaseModel


class CategoryStat(BaseModel):
    category: str
    count: int


class DashboardStats(BaseModel):
    total_contents: int
    processed_contents: int
    pending_contents: int
    top_categories: List[CategoryStat]
    recent_contents: int  # Last 7 days
    average_importance_score: float
