"""
Task Models

Data models for task management system.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID, uuid4


class TaskStatus(str, Enum):
    """Status of a task."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskCategory(str, Enum):
    """Categories of tasks."""
    DATA_GATHERING = "data_gathering"
    DOCUMENT_COLLECTION = "document_collection"
    DATA_ENTRY = "data_entry"
    REVIEW = "review"
    CALCULATION = "calculation"
    CLIENT_COMMUNICATION = "client_communication"
    SIGNATURE = "signature"
    FILING = "filing"
    FOLLOW_UP = "follow_up"
    ADMIN = "admin"
    CUSTOM = "custom"


@dataclass
class TaskComment:
    """Comment on a task."""
    id: UUID = field(default_factory=uuid4)
    task_id: UUID = None
    author_id: UUID = None
    author_name: str = ""
    content: str = ""
    is_internal: bool = True  # Internal = not visible to client
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "task_id": str(self.task_id) if self.task_id else None,
            "author_id": str(self.author_id) if self.author_id else None,
            "author_name": self.author_name,
            "content": self.content,
            "is_internal": self.is_internal,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class Task:
    """
    Represents a task in the CPA workflow.

    Tasks can be:
    - Assigned to staff members
    - Linked to clients and/or tax return sessions
    - Tracked with status and priority
    - Have due dates and reminders
    - Have comments for collaboration
    """
    id: UUID = field(default_factory=uuid4)
    firm_id: UUID = None

    # Task details
    title: str = ""
    description: Optional[str] = None
    category: TaskCategory = TaskCategory.CUSTOM

    # Relationships
    client_id: Optional[UUID] = None
    session_id: Optional[str] = None  # Tax return session
    deadline_id: Optional[UUID] = None  # Linked deadline
    parent_task_id: Optional[UUID] = None  # For subtasks

    # Assignment
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    created_by: Optional[UUID] = None
    created_by_name: Optional[str] = None

    # Status & Priority
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.NORMAL

    # Dates
    due_date: Optional[date] = None
    start_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[UUID] = None

    # Time tracking (optional, not enforced)
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None

    # Comments
    comments: List[TaskComment] = field(default_factory=list)

    # Checklist items (simple list of strings)
    checklist: List[Dict[str, Any]] = field(default_factory=list)

    # Tags for filtering
    tags: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def days_until_due(self) -> Optional[int]:
        """Calculate days until due date."""
        if not self.due_date:
            return None
        today = date.today()
        delta = self.due_date - today
        return delta.days

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date:
            return False
        if self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return False
        return self.days_until_due < 0

    @property
    def checklist_progress(self) -> Dict[str, int]:
        """Get checklist completion progress."""
        total = len(self.checklist)
        completed = sum(1 for item in self.checklist if item.get("completed", False))
        return {
            "total": total,
            "completed": completed,
            "percentage": int((completed / total * 100) if total > 0 else 0),
        }

    def add_comment(
        self,
        content: str,
        author_id: UUID = None,
        author_name: str = "",
        is_internal: bool = True,
    ) -> TaskComment:
        """Add a comment to the task."""
        comment = TaskComment(
            task_id=self.id,
            author_id=author_id,
            author_name=author_name,
            content=content,
            is_internal=is_internal,
        )
        self.comments.append(comment)
        self.updated_at = datetime.utcnow()
        return comment

    def add_checklist_item(self, text: str) -> Dict[str, Any]:
        """Add an item to the checklist."""
        item = {
            "id": str(uuid4()),
            "text": text,
            "completed": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.checklist.append(item)
        self.updated_at = datetime.utcnow()
        return item

    def toggle_checklist_item(self, item_id: str) -> bool:
        """Toggle a checklist item's completion status."""
        for item in self.checklist:
            if item.get("id") == item_id:
                item["completed"] = not item.get("completed", False)
                self.updated_at = datetime.utcnow()
                return True
        return False

    def mark_in_progress(self, user_id: UUID = None):
        """Mark task as in progress."""
        self.status = TaskStatus.IN_PROGRESS
        if not self.start_date:
            self.start_date = date.today()
        self.updated_at = datetime.utcnow()

    def mark_completed(self, user_id: UUID = None):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.completed_by = user_id
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "client_id": str(self.client_id) if self.client_id else None,
            "session_id": self.session_id,
            "deadline_id": str(self.deadline_id) if self.deadline_id else None,
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "assigned_to": str(self.assigned_to) if self.assigned_to else None,
            "assigned_to_name": self.assigned_to_name,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_by_name": self.created_by_name,
            "status": self.status.value,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "days_until_due": self.days_until_due,
            "is_overdue": self.is_overdue,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "comments": [c.to_dict() for c in self.comments],
            "comments_count": len(self.comments),
            "checklist": self.checklist,
            "checklist_progress": self.checklist_progress,
            "tags": self.tags,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_by": str(self.completed_by) if self.completed_by else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TaskTemplate:
    """
    Template for creating tasks.

    Used to create standardized tasks for common workflows.
    """
    id: UUID = field(default_factory=uuid4)
    firm_id: Optional[UUID] = None  # None = system template
    name: str = ""
    description: Optional[str] = None
    category: TaskCategory = TaskCategory.CUSTOM
    default_priority: TaskPriority = TaskPriority.NORMAL
    default_due_days: Optional[int] = None  # Days from creation
    checklist_template: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def create_task(
        self,
        firm_id: UUID,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        due_date: Optional[date] = None,
        created_by: Optional[UUID] = None,
    ) -> Task:
        """Create a task from this template."""
        # Calculate due date if not provided
        if not due_date and self.default_due_days:
            due_date = date.today() + timedelta(days=self.default_due_days)

        task = Task(
            firm_id=firm_id,
            title=self.name,
            description=self.description,
            category=self.category,
            client_id=client_id,
            session_id=session_id,
            assigned_to=assigned_to,
            priority=self.default_priority,
            due_date=due_date,
            tags=self.tags.copy(),
            created_by=created_by,
        )

        # Add checklist items from template
        for item_text in self.checklist_template:
            task.add_checklist_item(item_text)

        return task

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "default_priority": self.default_priority.value,
            "default_due_days": self.default_due_days,
            "checklist_template": self.checklist_template,
            "tags": self.tags,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


from datetime import timedelta

# Standard task templates
STANDARD_TEMPLATES = [
    TaskTemplate(
        name="Collect W-2s",
        description="Request and collect W-2 forms from client",
        category=TaskCategory.DOCUMENT_COLLECTION,
        default_priority=TaskPriority.HIGH,
        default_due_days=14,
        checklist_template=[
            "Send document request to client",
            "Follow up if not received within 7 days",
            "Verify W-2 information matches client records",
            "Upload and categorize documents",
        ],
        tags=["documents", "w-2", "income"],
    ),
    TaskTemplate(
        name="Collect 1099s",
        description="Request and collect all 1099 forms",
        category=TaskCategory.DOCUMENT_COLLECTION,
        default_priority=TaskPriority.HIGH,
        default_due_days=14,
        checklist_template=[
            "Send document request for all 1099 forms",
            "Check for 1099-INT, 1099-DIV, 1099-NEC, 1099-MISC",
            "Follow up on missing forms",
            "Verify totals with client",
        ],
        tags=["documents", "1099", "income"],
    ),
    TaskTemplate(
        name="Initial Data Review",
        description="Review client-provided data for completeness",
        category=TaskCategory.REVIEW,
        default_priority=TaskPriority.NORMAL,
        default_due_days=7,
        checklist_template=[
            "Review personal information",
            "Verify filing status",
            "Check dependent information",
            "Review income sources",
            "Check deduction eligibility",
            "Identify missing documents",
        ],
        tags=["review", "data-quality"],
    ),
    TaskTemplate(
        name="Prepare Tax Return",
        description="Complete tax return preparation",
        category=TaskCategory.CALCULATION,
        default_priority=TaskPriority.HIGH,
        default_due_days=14,
        checklist_template=[
            "Enter income information",
            "Enter deductions and credits",
            "Run calculations",
            "Review for accuracy",
            "Check for optimization opportunities",
            "Generate draft return",
        ],
        tags=["preparation", "calculation"],
    ),
    TaskTemplate(
        name="Partner Review",
        description="Partner review and approval of return",
        category=TaskCategory.REVIEW,
        default_priority=TaskPriority.HIGH,
        default_due_days=3,
        checklist_template=[
            "Review all income entries",
            "Verify deductions and credits",
            "Check calculations",
            "Review for compliance",
            "Approve or request changes",
        ],
        tags=["review", "approval", "partner"],
    ),
    TaskTemplate(
        name="Client Signature",
        description="Obtain client signature on return",
        category=TaskCategory.SIGNATURE,
        default_priority=TaskPriority.URGENT,
        default_due_days=7,
        checklist_template=[
            "Send return for review",
            "Answer client questions",
            "Send signature request",
            "Confirm signature received",
        ],
        tags=["signature", "client"],
    ),
    TaskTemplate(
        name="Follow Up - Missing Documents",
        description="Follow up with client on missing documents",
        category=TaskCategory.FOLLOW_UP,
        default_priority=TaskPriority.HIGH,
        default_due_days=3,
        checklist_template=[
            "Review what documents are still needed",
            "Contact client via preferred method",
            "Document follow-up attempt",
            "Schedule next follow-up if needed",
        ],
        tags=["follow-up", "documents"],
    ),
]
