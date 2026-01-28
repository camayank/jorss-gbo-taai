"""
Task Management Module for CPA Panel

Provides task-level management beyond return assignment:
- Task creation and assignment
- Task status workflow
- Due date tracking
- Task dependencies
- Task categories and templates
- Team collaboration
"""

from .task_service import TaskService, TaskStatus, TaskPriority, TaskCategory
from .task_models import Task, TaskComment, TaskTemplate

__all__ = [
    "TaskService",
    "TaskStatus",
    "TaskPriority",
    "TaskCategory",
    "Task",
    "TaskComment",
    "TaskTemplate",
]
