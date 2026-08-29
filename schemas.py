from datetime import date as Date
from typing import List, Optional
from pydantic import BaseModel


class EventCreate(BaseModel):
    date: Date
    start_hour: int
    end_hour: int
    label: str
    color: str = "#0E7C86"
    # Repeat presets: none | daily | weekdays | weekly | biweekly | monthly | custom
    repeat_type: str = "none"
    repeat_days: List[int] = []  # 0=Mon..6=Sun, used only when repeat_type == "custom"
    repeat_until: Optional[Date] = None  # if not set, capped at 1 year out for safety


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


class RoutineCreate(BaseModel):
    start_hour: int
    end_hour: int
    label: str
    color: str = "#5B9BF0"


class RoutineUpdate(BaseModel):
    start_hour: Optional[int] = None
    end_hour: Optional[int] = None
    label: Optional[str] = None
    color: Optional[str] = None


class RoutineOut(BaseModel):
    id: int
    start_hour: int
    end_hour: int
    label: str
    color: str
    sort_order: int

    class Config:
        from_attributes = True


class RoutineReorder(BaseModel):
    ids: List[int]  # full list of routine item ids in the new desired order


class RoutineSkipCreate(BaseModel):
    date: Date


class WeightEntryCreate(BaseModel):
    date: Date
    weight_kg: float


class WeightEntryOut(BaseModel):
    id: int
    date: Date
    weight_kg: float

    class Config:
        from_attributes = True


class WeightProfileUpdate(BaseModel):
    height_cm: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    activity_level: Optional[str] = None
    target_weight_kg: Optional[float] = None
    deficit_level: Optional[str] = None


class WeightProfileOut(BaseModel):
    height_cm: Optional[float] = None
    age: Optional[int] = None
    sex: str
    activity_level: str
    target_weight_kg: Optional[float] = None
    deficit_level: str

    class Config:
        from_attributes = True
