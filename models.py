import datetime
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class PlannerEvent(Base):
    """A block of time on a specific calendar date (e.g. 'Study: DBMS' on 2026-08-17, 9am-11am)."""
    __tablename__ = "planner_events"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True, nullable=False)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    label = Column(String, nullable=False)
    color = Column(String, default="#0E7C86")
    done = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)  # set when marked done -> powers history
    recurrence_group_id = Column(String, nullable=True, index=True)  # shared by weekly-repeat instances
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, default="#0E7C86")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    text = Column(String, nullable=False)
    done = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)  # set when marked done -> powers history
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    subject = relationship("Subject", back_populates="topics")


class Wish(Base):
    """A single wish-list item the user writes down and can check off."""
    __tablename__ = "wishes"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    done = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RoutineItem(Base):
    """A recurring daily routine block (e.g. 'Gym 6-7am') — not tied to any
    specific date. Applies every day until the user deletes it. sort_order
    controls the user-chosen display/priority order."""
    __tablename__ = "routine_items"

    id = Column(Integer, primary_key=True, index=True)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    label = Column(String, nullable=False)
    color = Column(String, default="#5B9BF0")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RoutineSkip(Base):
    """Marks a single RoutineItem as skipped on one specific date — the item
    itself is untouched and reappears normally the next day."""
    __tablename__ = "routine_skips"

    id = Column(Integer, primary_key=True, index=True)
    routine_item_id = Column(Integer, ForeignKey("routine_items.id"))
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
