from sqlalchemy.orm import Session
from app.models.task import TaskSequence


def generate_task_id(db: Session) -> str:
    """Insert a row into task_sequence to get the next auto-increment ID."""
    seq = TaskSequence()
    db.add(seq)
    db.flush()  # get the id without committing yet
    return f"TASK-{seq.id:04d}"
