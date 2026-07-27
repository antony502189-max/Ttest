from uuid import UUID

from pydantic import BaseModel


class MediaAssetResponse(BaseModel):
    id: UUID
    url: str
    mimeType: str
    sizeBytes: int
    width: int
    height: int
    kind: str
