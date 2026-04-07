"""
CRUD endpoints consumed by the Next.js frontend.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.task import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TaskOut(BaseModel):
    task_id: str
    timestamp: Optional[str]
    task_description: Optional[str]
    assigned_by: Optional[str]
    assignee_contact: Optional[str]
    assigned_to: Optional[str]
    employee_email_id: Optional[str]
    target_date: Optional[str]
    priority: Optional[str]
    approval_needed: Optional[int]
    client_name: Optional[str]
    department: Optional[str]
    assigned_name: Optional[str]
    assigned_email_id: Optional[str]
    comments: Optional[str]
    source_link: Optional[str]
    status: Optional[str]
    message_type: Optional[str]

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    employee_email_id: Optional[str] = None
    target_date: Optional[str] = None
    comments: Optional[str] = None
    approval_needed: Optional[int] = None
    department: Optional[str] = None
    client_name: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TaskOut])
def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if status:
        q = q.filter(Task.status == status)
    if priority:
        q = q.filter(Task.priority == priority)
    tasks = q.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for t in tasks:
        result.append(TaskOut(
            task_id=t.task_id,
            timestamp=t.timestamp.isoformat() if t.timestamp else None,
            task_description=t.task_description,
            assigned_by=t.assigned_by,
            assignee_contact=t.assignee_contact,
            assigned_to=t.assigned_to,
            employee_email_id=t.employee_email_id,
            target_date=str(t.target_date) if t.target_date else None,
            priority=t.priority,
            approval_needed=t.approval_needed,
            client_name=t.client_name,
            department=t.department,
            assigned_name=t.assigned_name,
            assigned_email_id=t.assigned_email_id,
            comments=t.comments,
            source_link=t.source_link,
            status=t.status,
            message_type=t.message_type,
        ))
    return result


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskOut(
        task_id=task.task_id,
        timestamp=task.timestamp.isoformat() if task.timestamp else None,
        task_description=task.task_description,
        assigned_by=task.assigned_by,
        assignee_contact=task.assignee_contact,
        assigned_to=task.assigned_to,
        employee_email_id=task.employee_email_id,
        target_date=str(task.target_date) if task.target_date else None,
        priority=task.priority,
        approval_needed=task.approval_needed,
        client_name=task.client_name,
        department=task.department,
        assigned_name=task.assigned_name,
        assigned_email_id=task.assigned_email_id,
        comments=task.comments,
        source_link=task.source_link,
        status=task.status,
        message_type=task.message_type,
    )


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, body: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return get_task(task_id, db)
