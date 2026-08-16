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
