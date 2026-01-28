"""
Task Service

Business logic for task management.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from collections import defaultdict

from .task_models import (
    Task,
    TaskComment,
    TaskTemplate,
    TaskStatus,
    TaskPriority,
    TaskCategory,
    STANDARD_TEMPLATES,
)

logger = logging.getLogger(__name__)


class TaskService:
    """
    Service for managing tasks.

    Provides:
    - Task CRUD operations
    - Task assignment and reassignment
    - Status workflow management
    - Task templates
    - Task analytics
    - Team workload view
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._tasks: Dict[UUID, Task] = {}
        self._templates: Dict[UUID, TaskTemplate] = {}

        # Initialize standard templates
        for template in STANDARD_TEMPLATES:
            self._templates[template.id] = template

    # =========================================================================
    # TASK CRUD
    # =========================================================================

    def create_task(
        self,
        firm_id: UUID,
        title: str,
        description: Optional[str] = None,
        category: TaskCategory = TaskCategory.CUSTOM,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        deadline_id: Optional[UUID] = None,
        parent_task_id: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        assigned_to_name: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        due_date: Optional[date] = None,
        estimated_hours: Optional[float] = None,
        tags: Optional[List[str]] = None,
        checklist: Optional[List[str]] = None,
        created_by: Optional[UUID] = None,
        created_by_name: Optional[str] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            firm_id: Tenant/firm ID
            title: Task title
            description: Task description
            category: Task category
            client_id: Associated client
            session_id: Associated tax return session
            deadline_id: Linked deadline
            parent_task_id: Parent task for subtasks
            assigned_to: Staff member assigned
            assigned_to_name: Name of assigned staff
            priority: Task priority
            due_date: Due date
            estimated_hours: Estimated hours to complete
            tags: Tags for filtering
            checklist: Initial checklist items
            created_by: User creating the task
            created_by_name: Name of creator

        Returns:
            Created Task object
        """
        task = Task(
            firm_id=firm_id,
            title=title,
            description=description,
            category=category,
            client_id=client_id,
            session_id=session_id,
            deadline_id=deadline_id,
            parent_task_id=parent_task_id,
            assigned_to=assigned_to,
            assigned_to_name=assigned_to_name,
            priority=priority,
            due_date=due_date,
            estimated_hours=estimated_hours,
            tags=tags or [],
            created_by=created_by,
            created_by_name=created_by_name,
        )

        # Add initial checklist items
        if checklist:
            for item_text in checklist:
                task.add_checklist_item(item_text)

        self._tasks[task.id] = task
        logger.info(f"Created task: {task.id} - {task.title}")

        return task

    def create_from_template(
        self,
        template_id: UUID,
        firm_id: UUID,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        due_date: Optional[date] = None,
        created_by: Optional[UUID] = None,
    ) -> Optional[Task]:
        """Create a task from a template."""
        template = self._templates.get(template_id)
        if not template:
            return None

        task = template.create_task(
            firm_id=firm_id,
            client_id=client_id,
            session_id=session_id,
            assigned_to=assigned_to,
            due_date=due_date,
            created_by=created_by,
        )

        self._tasks[task.id] = task
        logger.info(f"Created task from template: {task.id} - {task.title}")

        return task

    def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[TaskCategory] = None,
        priority: Optional[TaskPriority] = None,
        due_date: Optional[date] = None,
        estimated_hours: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Task]:
        """Update a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if category is not None:
            task.category = category
        if priority is not None:
            task.priority = priority
        if due_date is not None:
            task.due_date = due_date
        if estimated_hours is not None:
            task.estimated_hours = estimated_hours
        if tags is not None:
            task.tags = tags

        task.updated_at = datetime.utcnow()
        logger.info(f"Updated task: {task_id}")

        return task

    def delete_task(self, task_id: UUID) -> bool:
        """Delete a task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
        return False

    # =========================================================================
    # TASK ASSIGNMENT
    # =========================================================================

    def assign_task(
        self,
        task_id: UUID,
        assigned_to: UUID,
        assigned_to_name: Optional[str] = None,
    ) -> Optional[Task]:
        """Assign a task to a staff member."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.assigned_to = assigned_to
        task.assigned_to_name = assigned_to_name
        task.updated_at = datetime.utcnow()

        logger.info(f"Assigned task {task_id} to {assigned_to}")
        return task

    def unassign_task(self, task_id: UUID) -> Optional[Task]:
        """Remove assignment from a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.assigned_to = None
        task.assigned_to_name = None
        task.updated_at = datetime.utcnow()

        logger.info(f"Unassigned task {task_id}")
        return task

    def reassign_task(
        self,
        task_id: UUID,
        new_assignee: UUID,
        new_assignee_name: Optional[str] = None,
        add_comment: bool = True,
        reassigned_by: Optional[UUID] = None,
        reassigned_by_name: Optional[str] = None,
    ) -> Optional[Task]:
        """Reassign a task to a different staff member."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        old_assignee = task.assigned_to_name or str(task.assigned_to)

        task.assigned_to = new_assignee
        task.assigned_to_name = new_assignee_name
        task.updated_at = datetime.utcnow()

        # Add a comment about the reassignment
        if add_comment:
            task.add_comment(
                content=f"Task reassigned from {old_assignee} to {new_assignee_name or new_assignee}",
                author_id=reassigned_by,
                author_name=reassigned_by_name or "System",
                is_internal=True,
            )

        logger.info(f"Reassigned task {task_id} from {old_assignee} to {new_assignee}")
        return task

    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================

    def update_status(
        self,
        task_id: UUID,
        new_status: TaskStatus,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Task]:
        """Update task status."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        old_status = task.status
        task.status = new_status
        task.updated_at = datetime.utcnow()

        # Handle special status transitions
        if new_status == TaskStatus.IN_PROGRESS and not task.start_date:
            task.start_date = date.today()
        elif new_status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
            task.completed_by = updated_by

        logger.info(f"Task {task_id} status: {old_status.value} -> {new_status.value}")
        return task

    def start_task(self, task_id: UUID, user_id: Optional[UUID] = None) -> Optional[Task]:
        """Mark task as in progress."""
        return self.update_status(task_id, TaskStatus.IN_PROGRESS, user_id)

    def complete_task(self, task_id: UUID, user_id: Optional[UUID] = None) -> Optional[Task]:
        """Mark task as completed."""
        return self.update_status(task_id, TaskStatus.COMPLETED, user_id)

    def block_task(
        self,
        task_id: UUID,
        reason: str,
        blocked_by: Optional[UUID] = None,
        blocked_by_name: Optional[str] = None,
    ) -> Optional[Task]:
        """Mark task as blocked with reason."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.status = TaskStatus.BLOCKED
        task.updated_at = datetime.utcnow()

        # Add comment about block
        task.add_comment(
            content=f"Task blocked: {reason}",
            author_id=blocked_by,
            author_name=blocked_by_name or "System",
            is_internal=True,
        )

        logger.info(f"Task {task_id} blocked: {reason}")
        return task

    def unblock_task(
        self,
        task_id: UUID,
        unblocked_by: Optional[UUID] = None,
        unblocked_by_name: Optional[str] = None,
    ) -> Optional[Task]:
        """Unblock a task and return to in progress."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.utcnow()

        task.add_comment(
            content="Task unblocked",
            author_id=unblocked_by,
            author_name=unblocked_by_name or "System",
            is_internal=True,
        )

        logger.info(f"Task {task_id} unblocked")
        return task

    # =========================================================================
    # COMMENTS
    # =========================================================================

    def add_comment(
        self,
        task_id: UUID,
        content: str,
        author_id: Optional[UUID] = None,
        author_name: Optional[str] = None,
        is_internal: bool = True,
    ) -> Optional[TaskComment]:
        """Add a comment to a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        comment = task.add_comment(
            content=content,
            author_id=author_id,
            author_name=author_name or "Unknown",
            is_internal=is_internal,
        )

        return comment

    def delete_comment(self, task_id: UUID, comment_id: UUID) -> bool:
        """Delete a comment from a task."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        for i, comment in enumerate(task.comments):
            if comment.id == comment_id:
                del task.comments[i]
                task.updated_at = datetime.utcnow()
                return True

        return False

    # =========================================================================
    # CHECKLIST
    # =========================================================================

    def add_checklist_item(self, task_id: UUID, text: str) -> Optional[Dict[str, Any]]:
        """Add an item to task checklist."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        return task.add_checklist_item(text)

    def toggle_checklist_item(self, task_id: UUID, item_id: str) -> bool:
        """Toggle a checklist item."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        return task.toggle_checklist_item(item_id)

    def delete_checklist_item(self, task_id: UUID, item_id: str) -> bool:
        """Delete a checklist item."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        for i, item in enumerate(task.checklist):
            if item.get("id") == item_id:
                del task.checklist[i]
                task.updated_at = datetime.utcnow()
                return True

        return False

    # =========================================================================
    # TASK QUERIES
    # =========================================================================

    def get_tasks_for_firm(
        self,
        firm_id: UUID,
        status: Optional[TaskStatus] = None,
        category: Optional[TaskCategory] = None,
        priority: Optional[TaskPriority] = None,
        assigned_to: Optional[UUID] = None,
        client_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        include_completed: bool = False,
        tags: Optional[List[str]] = None,
    ) -> List[Task]:
        """Get tasks for a firm with optional filters."""
        tasks = []

        for task in self._tasks.values():
            if task.firm_id != firm_id:
                continue

            # Apply filters
            if status and task.status != status:
                continue
            if category and task.category != category:
                continue
            if priority and task.priority != priority:
                continue
            if assigned_to and task.assigned_to != assigned_to:
                continue
            if client_id and task.client_id != client_id:
                continue
            if session_id and task.session_id != session_id:
                continue
            if not include_completed and task.status == TaskStatus.COMPLETED:
                continue
            if tags:
                if not any(tag in task.tags for tag in tags):
                    continue

            tasks.append(task)

        # Sort by priority (urgent first) then due date
        priority_order = {
            TaskPriority.URGENT: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
        }
        tasks.sort(key=lambda t: (
            priority_order.get(t.priority, 2),
            t.due_date or date.max,
        ))

        return tasks

    def get_my_tasks(
        self,
        firm_id: UUID,
        user_id: UUID,
        include_completed: bool = False,
    ) -> List[Task]:
        """Get tasks assigned to a specific user."""
        return self.get_tasks_for_firm(
            firm_id=firm_id,
            assigned_to=user_id,
            include_completed=include_completed,
        )

    def get_unassigned_tasks(self, firm_id: UUID) -> List[Task]:
        """Get tasks without assignment."""
        return [
            t for t in self._tasks.values()
            if t.firm_id == firm_id and t.assigned_to is None
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]

    def get_overdue_tasks(self, firm_id: UUID) -> List[Task]:
        """Get all overdue tasks."""
        return [
            t for t in self._tasks.values()
            if t.firm_id == firm_id and t.is_overdue
        ]

    def get_tasks_for_client(
        self,
        firm_id: UUID,
        client_id: UUID,
        include_completed: bool = False,
    ) -> List[Task]:
        """Get all tasks for a client."""
        return self.get_tasks_for_firm(
            firm_id=firm_id,
            client_id=client_id,
            include_completed=include_completed,
        )

    def get_tasks_for_session(
        self,
        session_id: str,
        include_completed: bool = False,
    ) -> List[Task]:
        """Get all tasks for a tax return session."""
        return [
            t for t in self._tasks.values()
            if t.session_id == session_id
            and (include_completed or t.status != TaskStatus.COMPLETED)
        ]

    def get_subtasks(self, parent_task_id: UUID) -> List[Task]:
        """Get subtasks of a parent task."""
        return [
            t for t in self._tasks.values()
            if t.parent_task_id == parent_task_id
        ]

    # =========================================================================
    # TEMPLATES
    # =========================================================================

    def get_templates(
        self,
        firm_id: Optional[UUID] = None,
        category: Optional[TaskCategory] = None,
    ) -> List[TaskTemplate]:
        """Get available task templates."""
        templates = []

        for template in self._templates.values():
            if not template.is_active:
                continue
            # Include system templates (firm_id=None) and firm-specific templates
            if template.firm_id and template.firm_id != firm_id:
                continue
            if category and template.category != category:
                continue
            templates.append(template)

        return templates

    def create_template(
        self,
        firm_id: UUID,
        name: str,
        description: Optional[str] = None,
        category: TaskCategory = TaskCategory.CUSTOM,
        default_priority: TaskPriority = TaskPriority.NORMAL,
        default_due_days: Optional[int] = None,
        checklist_template: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> TaskTemplate:
        """Create a custom task template."""
        template = TaskTemplate(
            firm_id=firm_id,
            name=name,
            description=description,
            category=category,
            default_priority=default_priority,
            default_due_days=default_due_days,
            checklist_template=checklist_template or [],
            tags=tags or [],
        )

        self._templates[template.id] = template
        logger.info(f"Created template: {template.id} - {template.name}")

        return template

    # =========================================================================
    # ANALYTICS & WORKLOAD
    # =========================================================================

    def get_task_summary(self, firm_id: UUID) -> Dict[str, Any]:
        """Get summary statistics for tasks."""
        all_tasks = self.get_tasks_for_firm(firm_id, include_completed=True)

        by_status = defaultdict(int)
        by_category = defaultdict(int)
        by_priority = defaultdict(int)
        by_assignee = defaultdict(int)

        overdue_count = 0
        due_this_week = 0
        unassigned_count = 0

        today = date.today()
        week_end = today + timedelta(days=7)

        for task in all_tasks:
            by_status[task.status.value] += 1
            by_category[task.category.value] += 1
            by_priority[task.priority.value] += 1

            if task.assigned_to:
                by_assignee[str(task.assigned_to)] += 1
            else:
                unassigned_count += 1

            if task.is_overdue:
                overdue_count += 1

            if task.due_date and today <= task.due_date <= week_end:
                if task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                    due_this_week += 1

        completed = by_status.get("completed", 0)
        total_active = len(all_tasks) - completed - by_status.get("cancelled", 0)

        return {
            "total": len(all_tasks),
            "total_active": total_active,
            "overdue": overdue_count,
            "due_this_week": due_this_week,
            "unassigned": unassigned_count,
            "by_status": dict(by_status),
            "by_category": dict(by_category),
            "by_priority": dict(by_priority),
            "completion_rate": (completed / len(all_tasks) * 100) if all_tasks else 0,
        }

    def get_team_workload(self, firm_id: UUID) -> List[Dict[str, Any]]:
        """Get workload distribution across team members."""
        all_tasks = self.get_tasks_for_firm(firm_id, include_completed=False)

        workload = defaultdict(lambda: {
            "total": 0,
            "overdue": 0,
            "urgent": 0,
            "in_progress": 0,
            "estimated_hours": 0,
        })

        for task in all_tasks:
            if not task.assigned_to:
                continue

            key = str(task.assigned_to)
            workload[key]["total"] += 1
            workload[key]["name"] = task.assigned_to_name or key

            if task.is_overdue:
                workload[key]["overdue"] += 1
            if task.priority == TaskPriority.URGENT:
                workload[key]["urgent"] += 1
            if task.status == TaskStatus.IN_PROGRESS:
                workload[key]["in_progress"] += 1
            if task.estimated_hours:
                workload[key]["estimated_hours"] += task.estimated_hours

        return [
            {"user_id": k, **v}
            for k, v in workload.items()
        ]

    def get_kanban_view(self, firm_id: UUID) -> Dict[str, List[Dict[str, Any]]]:
        """Get tasks organized for kanban board display."""
        all_tasks = self.get_tasks_for_firm(firm_id, include_completed=True)

        kanban = {
            "todo": [],
            "in_progress": [],
            "in_review": [],
            "blocked": [],
            "completed": [],
        }

        for task in all_tasks:
            if task.status == TaskStatus.CANCELLED:
                continue
            kanban[task.status.value].append(task.to_dict())

        return kanban


# Global service instance
task_service = TaskService()
