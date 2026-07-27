from pydantic import BaseModel, Field


class SearchHistoryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=240)
