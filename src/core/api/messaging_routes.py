"""
Core Messaging API Routes

Unified messaging endpoints for all user types:
- Conversations and threads
- Direct messages
- Notifications
- Read receipts

Access control is automatically applied based on UserContext.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
from uuid import uuid4
import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from .auth_routes import get_current_user
from ..models.user import UserContext, UserType
from database.async_engine import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Core Messaging"])


# =============================================================================
# MODELS
# =============================================================================

class MessageType(str, Enum):
    TEXT = "text"
    DOCUMENT = "document"
    SYSTEM = "system"
    ACTION = "action"


class ConversationType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"
    SUPPORT = "support"
    TAX_RETURN = "tax_return"


class NotificationType(str, Enum):
    MESSAGE = "message"
    DOCUMENT_REQUEST = "document_request"
    TAX_RETURN_UPDATE = "tax_return_update"
    RECOMMENDATION = "recommendation"
    BILLING = "billing"
    SYSTEM = "system"


class Message(BaseModel):
    """Message model."""
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_type: UserType
    message_type: MessageType
    content: str
    attachments: List[dict] = []  # [{id, name, url, type}]
    read_by: List[str] = []
    created_at: datetime
    edited_at: Optional[datetime] = None


class Conversation(BaseModel):
    """Conversation/thread model."""
    id: str
    type: ConversationType
    subject: Optional[str] = None
    participants: List[dict]  # [{user_id, name, type}]
    tax_return_id: Optional[str] = None
    firm_id: Optional[str] = None
    last_message: Optional[Message] = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime


class Notification(BaseModel):
    """Notification model."""
    id: str
    user_id: str
    type: NotificationType
    title: str
    body: str
    data: dict = {}  # Additional context data
    read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None


class SendMessageRequest(BaseModel):
    """Request to send a message."""
    content: str
    message_type: MessageType = MessageType.TEXT
    attachments: List[str] = []  # Document IDs


class CreateConversationRequest(BaseModel):
    """Request to create a conversation."""
    type: ConversationType = ConversationType.DIRECT
    participant_ids: List[str]
    subject: Optional[str] = None
    tax_return_id: Optional[str] = None
    initial_message: Optional[str] = None


# =============================================================================
# DATABASE HELPER FUNCTIONS
# =============================================================================

def _parse_dt(val) -> Optional[datetime]:
    """Parse datetime from database value."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _user_type_to_str(user_type) -> str:
    """Convert UserType to string for JSON storage."""
    if isinstance(user_type, UserType):
        return user_type.value
    return str(user_type)


def _str_to_user_type(s: str) -> UserType:
    """Convert string back to UserType."""
    try:
        return UserType(s)
    except (ValueError, KeyError):
        return UserType.CONSUMER


async def _ensure_messaging_tables(session: AsyncSession):
    """Create messaging tables if they don't exist."""
    from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError

    # Check if conversations table exists
    try:
        check_query = text("SELECT 1 FROM conversations LIMIT 1")
        await session.execute(check_query)
    except (ProgrammingError, OperationalError):
        # Table doesn't exist - create it
        create_conversations = text("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id UUID PRIMARY KEY,
                conversation_type VARCHAR(50) NOT NULL,
                subject VARCHAR(500),
                participants JSONB NOT NULL DEFAULT '[]',
                tax_return_id UUID,
                firm_id UUID,
                last_message_id UUID,
                last_message_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            await session.execute(create_conversations)
            await session.commit()
            logger.info("Created conversations table")
        except SQLAlchemyError as e:
            logger.warning(f"Failed to create conversations table: {e}")
            await session.rollback()

    # Check if messages table exists
    try:
        check_query = text("SELECT 1 FROM messages LIMIT 1")
        await session.execute(check_query)
    except (ProgrammingError, OperationalError):
        create_messages = text("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id UUID PRIMARY KEY,
                conversation_id UUID NOT NULL,
                sender_id VARCHAR(255) NOT NULL,
                sender_name VARCHAR(255),
                sender_type VARCHAR(50),
                message_type VARCHAR(50) DEFAULT 'text',
                content TEXT NOT NULL,
                attachments JSONB DEFAULT '[]',
                read_by JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                edited_at TIMESTAMP
            )
        """)
        try:
            await session.execute(create_messages)
            await session.commit()
            logger.info("Created messages table")
        except SQLAlchemyError as e:
            logger.warning(f"Failed to create messages table: {e}")
            await session.rollback()

    # Check if notifications table exists
    try:
        check_query = text("SELECT 1 FROM notifications LIMIT 1")
        await session.execute(check_query)
    except (ProgrammingError, OperationalError):
        create_notifications = text("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id UUID PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                notification_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                body TEXT,
                data JSONB DEFAULT '{}',
                read BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        """)
        try:
            await session.execute(create_notifications)
            await session.commit()
            logger.info("Created notifications table")
        except SQLAlchemyError as e:
            logger.warning(f"Failed to create notifications table: {e}")
            await session.rollback()


def _row_to_conversation(row, messages_data: Optional[dict] = None) -> Conversation:
    """Convert database row to Conversation model."""
    # Row: conversation_id, conversation_type, subject, participants, tax_return_id,
    #      firm_id, last_message_id, last_message_data, created_at, updated_at
    participants = json.loads(row[3]) if row[3] and isinstance(row[3], str) else (row[3] or [])
    last_msg_data = json.loads(row[7]) if row[7] and isinstance(row[7], str) else row[7]

    last_message = None
    if last_msg_data:
        try:
            last_message = Message(
                id=last_msg_data.get("id", ""),
                conversation_id=str(row[0]),
                sender_id=last_msg_data.get("sender_id", ""),
                sender_name=last_msg_data.get("sender_name", ""),
                sender_type=_str_to_user_type(last_msg_data.get("sender_type", "consumer")),
                message_type=MessageType(last_msg_data.get("message_type", "text")),
                content=last_msg_data.get("content", ""),
                attachments=last_msg_data.get("attachments", []),
                read_by=last_msg_data.get("read_by", []),
                created_at=_parse_dt(last_msg_data.get("created_at")) or datetime.utcnow(),
                edited_at=_parse_dt(last_msg_data.get("edited_at")),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"Could not parse last message data: {e}")

    return Conversation(
        id=str(row[0]),
        type=ConversationType(row[1]) if row[1] else ConversationType.DIRECT,
        subject=row[2],
        participants=participants,
        tax_return_id=str(row[4]) if row[4] else None,
        firm_id=str(row[5]) if row[5] else None,
        last_message=last_message,
        unread_count=0,  # Calculated separately
        created_at=_parse_dt(row[8]) or datetime.utcnow(),
        updated_at=_parse_dt(row[9]) or datetime.utcnow(),
    )


def _row_to_message(row) -> Message:
    """Convert database row to Message model."""
    # Row: message_id, conversation_id, sender_id, sender_name, sender_type,
    #      message_type, content, attachments, read_by, created_at, edited_at
    attachments = json.loads(row[7]) if row[7] and isinstance(row[7], str) else (row[7] or [])
    read_by = json.loads(row[8]) if row[8] and isinstance(row[8], str) else (row[8] or [])

    return Message(
        id=str(row[0]),
        conversation_id=str(row[1]),
        sender_id=str(row[2]) if row[2] else "",
        sender_name=row[3] or "",
        sender_type=_str_to_user_type(row[4]) if row[4] else UserType.CONSUMER,
        message_type=MessageType(row[5]) if row[5] else MessageType.TEXT,
        content=row[6] or "",
        attachments=attachments,
        read_by=read_by,
        created_at=_parse_dt(row[9]) or datetime.utcnow(),
        edited_at=_parse_dt(row[10]),
    )


def _row_to_notification(row) -> Notification:
    """Convert database row to Notification model."""
    # Row: notification_id, user_id, notification_type, title, body, data, read, created_at, read_at
    data = json.loads(row[5]) if row[5] and isinstance(row[5], str) else (row[5] or {})

    return Notification(
        id=str(row[0]),
        user_id=str(row[1]) if row[1] else "",
        type=NotificationType(row[2]) if row[2] else NotificationType.SYSTEM,
        title=row[3] or "",
        body=row[4] or "",
        data=data,
        read=row[6] if row[6] is not None else False,
        created_at=_parse_dt(row[7]) or datetime.utcnow(),
        read_at=_parse_dt(row[8]),
    )


async def _can_access_conversation_db(context: UserContext, session: AsyncSession, conversation_id: str) -> bool:
    """Check if user can access a conversation."""
    if context.user_type == UserType.PLATFORM_ADMIN:
        return True

    query = text("""
        SELECT participants, firm_id
        FROM conversations
        WHERE conversation_id = :conversation_id
    """)
    result = await session.execute(query, {"conversation_id": conversation_id})
    row = result.fetchone()

    if not row:
        return False

    participants = json.loads(row[0]) if row[0] and isinstance(row[0], str) else (row[0] or [])
    firm_id = str(row[1]) if row[1] else None

    # Check if user is a participant
    for p in participants:
        if p.get("user_id") == context.user_id:
            return True

    # CPA team can access firm conversations
    if context.user_type == UserType.CPA_TEAM and firm_id == context.firm_id:
        return True

    return False


# =============================================================================
# CONVERSATIONS ENDPOINTS
# =============================================================================

@router.get("/conversations", response_model=List[Conversation])
async def list_conversations(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    type_filter: Optional[ConversationType] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List user's conversations.

    Returns conversations the user is a participant in.
    """
    await _ensure_messaging_tables(session)

    # Build access conditions
    conditions = []
    params = {"limit": limit, "offset": offset}

    if context.user_type == UserType.PLATFORM_ADMIN:
        conditions.append("1=1")
    elif context.user_type == UserType.CPA_TEAM:
        conditions.append(
            "(participants @> :participant_filter::jsonb OR firm_id = :firm_id)"
        )
        params["participant_filter"] = json.dumps([{"user_id": context.user_id}])
        params["firm_id"] = context.firm_id
    else:
        conditions.append("participants @> :participant_filter::jsonb")
        params["participant_filter"] = json.dumps([{"user_id": context.user_id}])

    if type_filter:
        conditions.append("conversation_type = :type_filter")
        params["type_filter"] = type_filter.value

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = text(f"""
        SELECT conversation_id, conversation_type, subject, participants, tax_return_id,
               firm_id, last_message_id, last_message_data, created_at, updated_at
        FROM conversations
        WHERE {where_clause}
        ORDER BY updated_at DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        result = await session.execute(query, params)
        rows = result.fetchall()

        results = []
        for row in rows:
            conv = _row_to_conversation(row)

            # Calculate unread count
            unread_query = text("""
                SELECT COUNT(*)
                FROM messages
                WHERE conversation_id = :conversation_id
                AND NOT (read_by @> :user_filter::jsonb)
            """)
            unread_result = await session.execute(unread_query, {
                "conversation_id": str(row[0]),
                "user_filter": json.dumps([context.user_id])
            })
            conv.unread_count = unread_result.scalar() or 0

            results.append(conv)

        return results
    except Exception as e:
        logger.warning(f"Error listing conversations: {e}")
        return []


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific conversation."""
    await _ensure_messaging_tables(session)

    query = text("""
        SELECT conversation_id, conversation_type, subject, participants, tax_return_id,
               firm_id, last_message_id, last_message_data, created_at, updated_at
        FROM conversations
        WHERE conversation_id = :conversation_id
    """)

    try:
        result = await session.execute(query, {"conversation_id": conversation_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        if not await _can_access_conversation_db(context, session, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return _row_to_conversation(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )


@router.post("/conversations", response_model=Conversation)
async def create_conversation(
    request: CreateConversationRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Create a new conversation.

    Creates a conversation with the specified participants.
    """
    await _ensure_messaging_tables(session)

    now = datetime.utcnow()
    conversation_id = str(uuid4())

    # Build participant list including the creator
    participants = [
        {"user_id": context.user_id, "name": context.full_name or "Unknown", "type": _user_type_to_str(context.user_type)}
    ]

    # Lookup participant details from database
    for pid in request.participant_ids:
        if pid != context.user_id:
            # Try to lookup user details
            user_query = text("""
                SELECT first_name, last_name, role FROM users WHERE user_id = :user_id
                UNION ALL
                SELECT first_name, last_name, 'client' FROM clients WHERE client_id = :user_id
                LIMIT 1
            """)
            try:
                user_result = await session.execute(user_query, {"user_id": pid})
                user_row = user_result.fetchone()
                if user_row:
                    name = f"{user_row[0] or ''} {user_row[1] or ''}".strip() or f"User {pid}"
                    user_type = UserType.CPA_TEAM if user_row[2] not in ('client', None) else UserType.CPA_CLIENT
                else:
                    name = f"User {pid}"
                    user_type = UserType.CONSUMER
            except (SQLAlchemyError, AttributeError) as e:
                logger.debug(f"Could not lookup user {pid}: {e}")
                name = f"User {pid}"
                user_type = UserType.CONSUMER

            participants.append({
                "user_id": pid,
                "name": name,
                "type": _user_type_to_str(user_type)
            })

    last_message_data = None
    message_id = None

    # Create initial message if provided
    if request.initial_message:
        message_id = str(uuid4())
        last_message_data = {
            "id": message_id,
            "sender_id": context.user_id,
            "sender_name": context.full_name or "Unknown",
            "sender_type": _user_type_to_str(context.user_type),
            "message_type": "text",
            "content": request.initial_message,
            "attachments": [],
            "read_by": [context.user_id],
            "created_at": now.isoformat(),
        }

    # Insert conversation
    insert_conv = text("""
        INSERT INTO conversations (
            conversation_id, conversation_type, subject, participants, tax_return_id,
            firm_id, last_message_id, last_message_data, created_at, updated_at
        ) VALUES (
            :conversation_id, :conversation_type, :subject, :participants, :tax_return_id,
            :firm_id, :last_message_id, :last_message_data, :created_at, :updated_at
        )
    """)

    await session.execute(insert_conv, {
        "conversation_id": conversation_id,
        "conversation_type": request.type.value,
        "subject": request.subject,
        "participants": json.dumps(participants),
        "tax_return_id": request.tax_return_id,
        "firm_id": context.firm_id,
        "last_message_id": message_id,
        "last_message_data": json.dumps(last_message_data) if last_message_data else None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })

    # Insert initial message if provided
    if request.initial_message and message_id:
        insert_msg = text("""
            INSERT INTO messages (
                message_id, conversation_id, sender_id, sender_name, sender_type,
                message_type, content, attachments, read_by, created_at
            ) VALUES (
                :message_id, :conversation_id, :sender_id, :sender_name, :sender_type,
                :message_type, :content, :attachments, :read_by, :created_at
            )
        """)

        await session.execute(insert_msg, {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "sender_id": context.user_id,
            "sender_name": context.full_name or "Unknown",
            "sender_type": _user_type_to_str(context.user_type),
            "message_type": "text",
            "content": request.initial_message,
            "attachments": json.dumps([]),
            "read_by": json.dumps([context.user_id]),
            "created_at": now.isoformat(),
        })

    await session.commit()

    last_message = None
    if last_message_data:
        last_message = Message(
            id=message_id,
            conversation_id=conversation_id,
            sender_id=context.user_id,
            sender_name=context.full_name or "Unknown",
            sender_type=context.user_type,
            message_type=MessageType.TEXT,
            content=request.initial_message,
            read_by=[context.user_id],
            created_at=now
        )

    conversation = Conversation(
        id=conversation_id,
        type=request.type,
        subject=request.subject,
        participants=participants,
        tax_return_id=request.tax_return_id,
        firm_id=context.firm_id,
        last_message=last_message,
        created_at=now,
        updated_at=now
    )

    logger.info(f"Conversation created: {conversation_id}")

    return conversation


# =============================================================================
# MESSAGES ENDPOINTS
# =============================================================================

@router.get("/conversations/{conversation_id}/messages", response_model=List[Message])
async def list_messages(
    conversation_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    before: Optional[datetime] = None,
    limit: int = Query(50, le=100)
):
    """
    Get messages in a conversation.

    Returns messages in reverse chronological order.
    """
    await _ensure_messaging_tables(session)

    if not await _can_access_conversation_db(context, session, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    conditions = ["conversation_id = :conversation_id"]
    params = {"conversation_id": conversation_id, "limit": limit}

    if before:
        conditions.append("created_at < :before")
        params["before"] = before.isoformat()

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT message_id, conversation_id, sender_id, sender_name, sender_type,
               message_type, content, attachments, read_by, created_at, edited_at
        FROM messages
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    try:
        result = await session.execute(query, params)
        rows = result.fetchall()
        return [_row_to_message(row) for row in rows]
    except Exception as e:
        logger.warning(f"Error listing messages: {e}")
        return []


@router.post("/conversations/{conversation_id}/messages", response_model=Message)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Send a message in a conversation.

    Supports text messages and document attachments.
    """
    await _ensure_messaging_tables(session)

    if not await _can_access_conversation_db(context, session, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    now = datetime.utcnow()
    message_id = str(uuid4())

    # Build attachments (in production, would validate document IDs)
    attachments = [
        {"id": doc_id, "name": f"Document {doc_id}", "type": "application/pdf"}
        for doc_id in request.attachments
    ]

    # Insert message
    insert_msg = text("""
        INSERT INTO messages (
            message_id, conversation_id, sender_id, sender_name, sender_type,
            message_type, content, attachments, read_by, created_at
        ) VALUES (
            :message_id, :conversation_id, :sender_id, :sender_name, :sender_type,
            :message_type, :content, :attachments, :read_by, :created_at
        )
    """)

    await session.execute(insert_msg, {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_id": context.user_id,
        "sender_name": context.full_name or "Unknown",
        "sender_type": _user_type_to_str(context.user_type),
        "message_type": request.message_type.value,
        "content": request.content,
        "attachments": json.dumps(attachments),
        "read_by": json.dumps([context.user_id]),
        "created_at": now.isoformat(),
    })

    # Update conversation's last message
    last_message_data = {
        "id": message_id,
        "sender_id": context.user_id,
        "sender_name": context.full_name or "Unknown",
        "sender_type": _user_type_to_str(context.user_type),
        "message_type": request.message_type.value,
        "content": request.content,
        "attachments": attachments,
        "read_by": [context.user_id],
        "created_at": now.isoformat(),
    }

    update_conv = text("""
        UPDATE conversations SET
            last_message_id = :message_id,
            last_message_data = :last_message_data,
            updated_at = :updated_at
        WHERE conversation_id = :conversation_id
    """)

    await session.execute(update_conv, {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "last_message_data": json.dumps(last_message_data),
        "updated_at": now.isoformat(),
    })

    # Get conversation participants for notifications
    conv_query = text("SELECT participants FROM conversations WHERE conversation_id = :conversation_id")
    conv_result = await session.execute(conv_query, {"conversation_id": conversation_id})
    conv_row = conv_result.fetchone()

    if conv_row:
        participants = json.loads(conv_row[0]) if conv_row[0] and isinstance(conv_row[0], str) else (conv_row[0] or [])

        # Create notifications for other participants
        for participant in participants:
            if participant.get("user_id") != context.user_id:
                notif_id = str(uuid4())
                insert_notif = text("""
                    INSERT INTO notifications (
                        notification_id, user_id, notification_type, title, body, data, created_at
                    ) VALUES (
                        :notification_id, :user_id, :notification_type, :title, :body, :data, :created_at
                    )
                """)

                await session.execute(insert_notif, {
                    "notification_id": notif_id,
                    "user_id": participant.get("user_id"),
                    "notification_type": "message",
                    "title": f"New message from {context.full_name or 'Unknown'}",
                    "body": request.content[:100] + "..." if len(request.content) > 100 else request.content,
                    "data": json.dumps({"conversation_id": conversation_id, "message_id": message_id}),
                    "created_at": now.isoformat(),
                })

    await session.commit()

    message = Message(
        id=message_id,
        conversation_id=conversation_id,
        sender_id=context.user_id,
        sender_name=context.full_name or "Unknown",
        sender_type=context.user_type,
        message_type=request.message_type,
        content=request.content,
        attachments=attachments,
        read_by=[context.user_id],
        created_at=now
    )

    logger.info(f"Message sent in conversation: {conversation_id}")

    return message


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Mark all messages in a conversation as read.

    Updates read receipts for all unread messages.
    """
    await _ensure_messaging_tables(session)

    if not await _can_access_conversation_db(context, session, conversation_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Update all messages in the conversation to include user in read_by
    # PostgreSQL JSONB array append
    update_query = text("""
        UPDATE messages SET
            read_by = CASE
                WHEN read_by @> :user_filter::jsonb THEN read_by
                ELSE read_by || :user_id::jsonb
            END
        WHERE conversation_id = :conversation_id
        AND NOT (read_by @> :user_filter::jsonb)
    """)

    result = await session.execute(update_query, {
        "conversation_id": conversation_id,
        "user_filter": json.dumps([context.user_id]),
        "user_id": json.dumps(context.user_id),
    })
    read_count = result.rowcount

    await session.commit()

    return {"success": True, "messages_marked_read": read_count}


# =============================================================================
# NOTIFICATIONS ENDPOINTS
# =============================================================================

@router.get("/notifications", response_model=List[Notification])
async def list_notifications(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    unread_only: bool = False,
    type_filter: Optional[NotificationType] = None,
    limit: int = Query(50, le=100),
    offset: int = 0
):
    """
    List user's notifications.

    Returns notifications in reverse chronological order.
    """
    await _ensure_messaging_tables(session)

    conditions = ["user_id = :user_id"]
    params = {"user_id": context.user_id, "limit": limit, "offset": offset}

    if unread_only:
        conditions.append("read = false")

    if type_filter:
        conditions.append("notification_type = :type_filter")
        params["type_filter"] = type_filter.value

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT notification_id, user_id, notification_type, title, body, data, read, created_at, read_at
        FROM notifications
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        result = await session.execute(query, params)
        rows = result.fetchall()
        return [_row_to_notification(row) for row in rows]
    except Exception as e:
        logger.warning(f"Error listing notifications: {e}")
        return []


@router.get("/notifications/unread-count")
async def get_unread_count(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get count of unread notifications."""
    await _ensure_messaging_tables(session)

    query = text("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = :user_id AND read = false
    """)

    try:
        result = await session.execute(query, {"user_id": context.user_id})
        count = result.scalar() or 0
        return {"unread_count": count}
    except Exception:
        return {"unread_count": 0}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Mark a notification as read."""
    await _ensure_messaging_tables(session)

    # First check if notification exists and belongs to user
    check_query = text("""
        SELECT user_id FROM notifications WHERE notification_id = :notification_id
    """)
    result = await session.execute(check_query, {"notification_id": notification_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    if str(row[0]) != context.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    update_query = text("""
        UPDATE notifications SET
            read = true,
            read_at = :read_at
        WHERE notification_id = :notification_id
    """)

    await session.execute(update_query, {
        "notification_id": notification_id,
        "read_at": datetime.utcnow().isoformat(),
    })
    await session.commit()

    return {"success": True}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Mark all notifications as read."""
    await _ensure_messaging_tables(session)

    now = datetime.utcnow()

    update_query = text("""
        UPDATE notifications SET
            read = true,
            read_at = :read_at
        WHERE user_id = :user_id AND read = false
    """)

    result = await session.execute(update_query, {
        "user_id": context.user_id,
        "read_at": now.isoformat(),
    })
    count = result.rowcount

    await session.commit()

    return {"success": True, "notifications_marked_read": count}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a notification."""
    await _ensure_messaging_tables(session)

    # First check if notification exists and belongs to user
    check_query = text("""
        SELECT user_id FROM notifications WHERE notification_id = :notification_id
    """)
    result = await session.execute(check_query, {"notification_id": notification_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    if str(row[0]) != context.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    delete_query = text("DELETE FROM notifications WHERE notification_id = :notification_id")
    await session.execute(delete_query, {"notification_id": notification_id})
    await session.commit()

    return {"success": True}


# =============================================================================
# QUICK ACTIONS
# =============================================================================

@router.post("/quick-message")
async def send_quick_message(
    recipient_id: str,
    message: str,
    context: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Send a quick message to a user.

    Creates a conversation if one doesn't exist, then sends the message.
    """
    await _ensure_messaging_tables(session)

    now = datetime.utcnow()

    # Find existing direct conversation between these users
    find_conv_query = text("""
        SELECT conversation_id
        FROM conversations
        WHERE conversation_type = 'direct'
        AND participants @> :participant1::jsonb
        AND participants @> :participant2::jsonb
        LIMIT 1
    """)

    result = await session.execute(find_conv_query, {
        "participant1": json.dumps([{"user_id": context.user_id}]),
        "participant2": json.dumps([{"user_id": recipient_id}]),
    })
    existing_row = result.fetchone()

    conversation_id = str(existing_row[0]) if existing_row else None

    if not conversation_id:
        # Create new conversation
        conversation_id = str(uuid4())

        # Lookup recipient details
        user_query = text("""
            SELECT first_name, last_name, role FROM users WHERE user_id = :user_id
            UNION ALL
            SELECT first_name, last_name, 'client' FROM clients WHERE client_id = :user_id
            LIMIT 1
        """)
        try:
            user_result = await session.execute(user_query, {"user_id": recipient_id})
            user_row = user_result.fetchone()
            if user_row:
                recipient_name = f"{user_row[0] or ''} {user_row[1] or ''}".strip() or f"User {recipient_id}"
                recipient_type = UserType.CPA_TEAM if user_row[2] not in ('client', None) else UserType.CPA_CLIENT
            else:
                recipient_name = f"User {recipient_id}"
                recipient_type = UserType.CONSUMER
        except Exception:
            recipient_name = f"User {recipient_id}"
            recipient_type = UserType.CONSUMER

        participants = [
            {"user_id": context.user_id, "name": context.full_name or "Unknown", "type": _user_type_to_str(context.user_type)},
            {"user_id": recipient_id, "name": recipient_name, "type": _user_type_to_str(recipient_type)}
        ]

        insert_conv = text("""
            INSERT INTO conversations (
                conversation_id, conversation_type, participants, firm_id, created_at, updated_at
            ) VALUES (
                :conversation_id, :conversation_type, :participants, :firm_id, :created_at, :updated_at
            )
        """)

        await session.execute(insert_conv, {
            "conversation_id": conversation_id,
            "conversation_type": "direct",
            "participants": json.dumps(participants),
            "firm_id": context.firm_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

    # Send message
    message_id = str(uuid4())

    insert_msg = text("""
        INSERT INTO messages (
            message_id, conversation_id, sender_id, sender_name, sender_type,
            message_type, content, attachments, read_by, created_at
        ) VALUES (
            :message_id, :conversation_id, :sender_id, :sender_name, :sender_type,
            :message_type, :content, :attachments, :read_by, :created_at
        )
    """)

    await session.execute(insert_msg, {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_id": context.user_id,
        "sender_name": context.full_name or "Unknown",
        "sender_type": _user_type_to_str(context.user_type),
        "message_type": "text",
        "content": message,
        "attachments": json.dumps([]),
        "read_by": json.dumps([context.user_id]),
        "created_at": now.isoformat(),
    })

    # Update conversation's last message
    last_message_data = {
        "id": message_id,
        "sender_id": context.user_id,
        "sender_name": context.full_name or "Unknown",
        "sender_type": _user_type_to_str(context.user_type),
        "message_type": "text",
        "content": message,
        "attachments": [],
        "read_by": [context.user_id],
        "created_at": now.isoformat(),
    }

    update_conv = text("""
        UPDATE conversations SET
            last_message_id = :message_id,
            last_message_data = :last_message_data,
            updated_at = :updated_at
        WHERE conversation_id = :conversation_id
    """)

    await session.execute(update_conv, {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "last_message_data": json.dumps(last_message_data),
        "updated_at": now.isoformat(),
    })

    # Create notification for recipient
    notif_id = str(uuid4())
    insert_notif = text("""
        INSERT INTO notifications (
            notification_id, user_id, notification_type, title, body, data, created_at
        ) VALUES (
            :notification_id, :user_id, :notification_type, :title, :body, :data, :created_at
        )
    """)

    await session.execute(insert_notif, {
        "notification_id": notif_id,
        "user_id": recipient_id,
        "notification_type": "message",
        "title": f"New message from {context.full_name or 'Unknown'}",
        "body": message[:100] + "..." if len(message) > 100 else message,
        "data": json.dumps({"conversation_id": conversation_id}),
        "created_at": now.isoformat(),
    })

    await session.commit()

    return {
        "success": True,
        "conversation_id": conversation_id,
        "message_id": message_id
    }
