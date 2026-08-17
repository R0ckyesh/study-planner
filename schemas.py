from datetime import date as Date
from typing import List, Optional
from pydantic import BaseModel


class EventCreate(BaseModel):
    date: Date
    start_hour: int
    end_hour: int
    label: str
    color: str = "#0E7C86"
    repeat_weekly: bool = False
    repeat_weeks: int = 12  # how many weeks total (including the first) when repeat_weekly is true


class EventUpdate(BaseModel):
    date: Optional[Date] = None
    label: Optional[str] = None
    color: Optional[str] = None
    done: Optional[bool] = None
    start_hour: Optional[int] = None
    end_hour: Optional[int] = None


class EventOut(BaseModel):
    id: int
    date: Date
    start_hour: int
    end_hour: int
    label: str
    color: str
    done: bool
    recurrence_group_id: Optional[str] = None

    class Config:
        from_attributes = True


class TopicCreate(BaseModel):
    lines: List[str]


class TopicOut(BaseModel):
    id: int
    text: str
    done: bool

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    name: str
    color: str = "#0E7C86"


class SubjectOut(BaseModel):
    id: int
    name: str
    color: str
    topics: List[TopicOut] = []

    class Config:
        from_attributes = True


class WishCreate(BaseModel):
    text: str


class WishBulkCreate(BaseModel):
    lines: List[str]


class WishOut(BaseModel):
    id: int
    text: str
    done: bool

    class Config:
        from_attributes = True
