from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from backend.database import Base


class ResearchPaper(Base):
    __tablename__ = "research_papers"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    content_json = Column(JSON, nullable=True)
    file_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    analysis_status = Column(String, nullable=True)


class AIInsight(Base):
    __tablename__ = "ai_insights"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("research_papers.id"), nullable=False)

    summary = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    paper = relationship("ResearchPaper", backref="ai_insights")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("research_papers.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    paper = relationship("ResearchPaper", backref="chat_messages")
