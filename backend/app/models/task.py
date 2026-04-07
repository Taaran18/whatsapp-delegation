from datetime import date, datetime
from sqlalchemy import Column, Date, DateTime, Enum, Integer, String, Text, func
from app.models.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    task_id             = Column(String(50), unique=True, nullable=False)
    timestamp           = Column(DateTime, default=func.now())
    task_description    = Column(Text)
    assigned_by         = Column(String(255))
    assignee_contact    = Column(String(50))
    assigned_to         = Column(String(255))
    employee_email_id   = Column(String(255))
    target_date         = Column(Date)
    priority            = Column(Enum("Low", "Medium", "High", "Critical"), default="Medium")
    approval_needed     = Column(Integer, default=0)
    client_name         = Column(String(255))
    department          = Column(String(255))
    assigned_name       = Column(String(255))
    assigned_email_id   = Column(String(255))
    comments            = Column(Text)
    source_link         = Column(String(500))
    message_type        = Column(Enum("text", "voice"), default="text")
    raw_message         = Column(Text)
    status              = Column(
        Enum("Pending", "In Progress", "Completed", "Cancelled"), default="Pending"
    )
    created_at          = Column(DateTime, default=func.now())
    updated_at          = Column(DateTime, default=func.now(), onupdate=func.now())


class MessageLog(Base):
    __tablename__ = "message_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    wa_message_id   = Column(String(100), unique=True)
    sender_number   = Column(String(50))
    message_type    = Column(Enum("text", "voice", "other"), default="other")
    raw_payload     = Column(Text)  # stored as JSON string
    processed       = Column(Integer, default=0)
    task_id         = Column(String(50))
    error_message   = Column(Text)
    received_at     = Column(DateTime, default=func.now())


class Employee(Base):
    __tablename__ = "employees"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    whatsapp_number   = Column(String(50), unique=True, nullable=False)
    name              = Column(String(255), nullable=False)
    email             = Column(String(255))
    department        = Column(String(255))
    role              = Column(String(255))
    created_at        = Column(DateTime, default=func.now())


class TaskSequence(Base):
    __tablename__ = "task_sequence"
    id = Column(Integer, primary_key=True, autoincrement=True)
