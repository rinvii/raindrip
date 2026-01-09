from typing import List, Optional
from pydantic import BaseModel, Field


class Collection(BaseModel):
    id: int = Field(alias="_id")
    title: str
    count: Optional[int] = 0
    parent: Optional[dict] = None  # Contains {"$id": int}
    view: Optional[str] = None
    public: Optional[bool] = None
    expanded: Optional[bool] = None
    sort: Optional[int] = None
    cover: Optional[List[str]] = None
    created: Optional[str] = None
    lastUpdate: Optional[str] = None
    color: Optional[str] = None
    access: Optional[dict] = None
    collaborators: Optional[dict] = None
    user: Optional[dict] = None


class CollectionCreate(BaseModel):
    title: str
    view: Optional[str] = None
    public: Optional[bool] = None
    parent: Optional[dict] = None  # Expecting {"$id": int} if set


class CollectionUpdate(BaseModel):
    title: Optional[str] = None
    view: Optional[str] = None
    public: Optional[bool] = None
    parent: Optional[dict] = None
    expanded: Optional[bool] = None


class Raindrop(BaseModel):
    id: int = Field(alias="_id")
    link: str
    title: str = ""
    excerpt: str = ""
    note: str = ""
    tags: List[str] = []
    cover: Optional[str] = None
    created: Optional[str] = None
    lastUpdate: Optional[str] = None
    type: Optional[str] = "link"  # link, article, image, video, document, audio
    important: Optional[bool] = False
    collection_id: int = Field(alias="collectionId", default=-1)
    domain: Optional[str] = None
    media: Optional[List[dict]] = None
    broken: Optional[bool] = False


class RaindropUpdate(BaseModel):
    link: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None
    collectionId: Optional[int] = None
    collection: Optional[dict] = None  # Expected structure: {"$id": int}


class AccountStructure(BaseModel):
    collections: List[Collection]
    tags: List[str]
