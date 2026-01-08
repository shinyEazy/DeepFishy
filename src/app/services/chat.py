"""Chat service for managing conversations and agent interactions."""

from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import json

from app.db.models.conversation import Conversation, Message
from app.core.logging import logger


class ChatService:
    """Service for managing chat conversations and agent interactions."""

    def __init__(self, db: Session):
        """
        Initialize chat service.

        Args:
            db: Database session
        """
        self.db = db

    def create_conversation(self, title: Optional[str] = None) -> Conversation:
        """
        Create a new conversation.

        Args:
            title: Optional conversation title

        Returns:
            Created conversation
        """
        try:
            conversation = Conversation(title=title or "New Conversation", meta={})
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

            logger.info(f"Created conversation: {conversation.id}")
            return conversation

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create conversation: {e}")
            raise

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID, including its messages.

        Uses eager-loading to avoid N+1 query problems when accessing messages.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation or None if not found
        """
        try:
            return (
                self.db.query(Conversation)
                .options(joinedload(Conversation.messages))
                .filter(Conversation.id == conversation_id)
                .first()
            )
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    def get_or_create_conversation(
        self, conversation_id: Optional[str] = None
    ) -> Conversation:
        """
        Get existing conversation or create new one.

        Args:
            conversation_id: Optional conversation ID

        Returns:
            Conversation (existing or new)
        """
        if conversation_id:
            conversation = self.get_conversation(conversation_id)
            if conversation:
                return conversation
            logger.warning(
                f"Conversation {conversation_id} not found, creating new one"
            )

        return self.create_conversation()

    def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """
        List conversations ordered by most recent.

        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List of conversations
        """
        try:
            return (
                self.db.query(Conversation)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    def list_conversations_with_counts(
        self, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Tuple[Conversation, int]], int]:
        """
        List conversations with message counts in a single optimized query.

        Uses a single query with JOIN and GROUP BY to efficiently get conversation
        data with message counts, avoiding the N+1 query problem.

        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            Tuple of (list of (conversation, message_count) tuples, total_count)
        """
        try:
            # Get total count of all conversations
            total_count = self.db.query(func.count(Conversation.id)).scalar() or 0

            # Query for conversations with message counts using a join and group by
            results = (
                self.db.query(
                    Conversation, func.count(Message.id).label("message_count")
                )
                .outerjoin(Message, Conversation.id == Message.conversation_id)
                .group_by(Conversation.id)
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            return results, total_count

        except Exception as e:
            logger.error(f"Failed to list conversations with counts: {e}")
            return [], 0

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete conversation and all its messages.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            conversation = self.get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                return False

            self.db.delete(conversation)
            self.db.commit()
            logger.info(f"Deleted conversation: {conversation_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Save a message to the conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata

        Returns:
            Created message
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                meta=metadata or {},
            )
            self.db.add(message)

            # Update conversation's updated_at timestamp
            self.db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).update({"updated_at": datetime.utcnow()})

            self.db.commit()
            self.db.refresh(message)

            logger.debug(f"Saved {role} message to conversation {conversation_id}")
            return message

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save message: {e}")
            raise

    def get_messages(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> List[Message]:
        """
        Get messages for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Optional limit on number of messages

        Returns:
            List of messages ordered by creation time
        """
        try:
            query = (
                self.db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            logger.error(f"Failed to get messages for {conversation_id}: {e}")
            return []

    async def chat_completion(
        self, message: str, conversation_id: Optional[str] = None, stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a chat message and get agent response.

        Args:
            message: User message
            conversation_id: Optional conversation ID
            stream: Whether to stream the response

        Returns:
            Dictionary with conversation_id, response message, and metadata
        """
        try:
            # Import agent here to avoid circular imports
            from app.engine.main import agent

            # Get or create conversation
            conversation = self.get_or_create_conversation(conversation_id)

            # Save user message
            self.save_message(
                conversation_id=conversation.id, role="user", content=message
            )

            # Invoke agent
            logger.info(f"Invoking agent for conversation {conversation.id}")

            if stream:
                # Not fully implemented - agent doesn't support streaming yet
                # For now, we'll return complete response
                logger.warning(
                    "Streaming not fully supported, returning complete response"
                )

            # Call agent with the user message
            agent_response = agent.invoke(
                {"messages": [{"role": "user", "content": message}]}
            )

            # Extract response content
            if isinstance(agent_response, dict):
                # Handle different response formats
                if "messages" in agent_response and agent_response["messages"]:
                    last_message = agent_response["messages"][-1]
                    if isinstance(last_message, dict):
                        response_content = last_message.get(
                            "content", str(agent_response)
                        )
                    else:
                        response_content = str(
                            last_message.content
                            if hasattr(last_message, "content")
                            else last_message
                        )
                else:
                    response_content = str(agent_response)
            else:
                response_content = str(agent_response)

            # Save assistant message
            assistant_message = self.save_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
                metadata={"agent_response": True},
            )

            logger.info(
                f"Chat completion successful for conversation {conversation.id}"
            )

            return {
                "conversation_id": conversation.id,
                "message": response_content,
                "message_id": assistant_message.id,
                "created_at": assistant_message.created_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Chat completion failed: {e}", exc_info=True)
            raise

    async def chat_completion_stream(
        self, message: str, conversation_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat message and stream the agent response.

        Args:
            message: User message
            conversation_id: Optional conversation ID

        Yields:
            Server-Sent Events formatted strings
        """
        try:
            # Import agent here to avoid circular imports
            from app.engine.main import agent

            # Get or create conversation
            conversation = self.get_or_create_conversation(conversation_id)

            # Save user message
            self.save_message(
                conversation_id=conversation.id, role="user", content=message
            )

            logger.info(f"Starting streaming for conversation {conversation.id}")

            # Send conversation_id first
            yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation.id})}\n\n"

            # For now, invoke agent and stream the complete response
            # In future, can integrate with agent.astream() if available
            agent_response = agent.invoke(
                {"messages": [{"role": "user", "content": message}]}
            )

            # Extract response content
            if isinstance(agent_response, dict):
                if "messages" in agent_response and agent_response["messages"]:
                    last_message = agent_response["messages"][-1]
                    if isinstance(last_message, dict):
                        response_content = last_message.get(
                            "content", str(agent_response)
                        )
                    else:
                        response_content = str(
                            last_message.content
                            if hasattr(last_message, "content")
                            else last_message
                        )
                else:
                    response_content = str(agent_response)
            else:
                response_content = str(agent_response)

            # Stream the response (chunked by words for demo)
            words = response_content.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

            # Save assistant message
            assistant_message = self.save_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
                metadata={"agent_response": True, "streamed": True},
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_message.id})}\n\n"

            logger.info(f"Streaming completed for conversation {conversation.id}")

        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            error_data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {error_data}\n\n"
