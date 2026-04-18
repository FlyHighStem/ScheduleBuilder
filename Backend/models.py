from sqlalchemy import Column, Integer, String
from database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key = True, index = True)
    title = Column(String)
    priority = Column(Integer)
    duration = Column(Integer)