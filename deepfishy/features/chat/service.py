"""Chat service for managing conversations and agent interactions."""

from datetime import datetime
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from db.models.conversation import Conversation, Message
from deepfishy.shared.logging import logger

DEFAULT_CONVERSATION_TITLE = "Cuộc trò chuyện mới"


class ChatService:
    """Service for managing chat conversations and agent interactions."""

    def __init__(self, db: Session):
        self.db = db

    def create_conversation(self, title: Optional[str] = None) -> Conversation:
        try:
            conversation = Conversation(
                title=title or DEFAULT_CONVERSATION_TITLE, meta={}
            )
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
        if conversation_id:
            conversation = self.get_conversation(conversation_id)
            if conversation:
                return conversation
            logger.warning(
                f"Conversation {conversation_id} not found, creating new one"
            )

        return self.create_conversation()

    def build_conversation_title(self, content: str, max_length: int = 80) -> str:
        normalized = " ".join(content.split()).strip()
        if not normalized:
            return DEFAULT_CONVERSATION_TITLE

        if len(normalized) <= max_length:
            return normalized

        return normalized[: max_length - 1].rstrip() + "…"

    def ensure_conversation_title(
        self, conversation: Conversation, seed_text: str
    ) -> Conversation:
        current_title = (conversation.title or "").strip()
        if current_title and current_title not in {
            DEFAULT_CONVERSATION_TITLE,
            "New Conversation",
        }:
            return conversation

        try:
            conversation.title = self.build_conversation_title(seed_text)
            conversation.updated_at = datetime.utcnow()
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update conversation title: {e}")
            raise

    def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
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
        try:
            total_count = self.db.query(func.count(Conversation.id)).scalar() or 0
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
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                meta=metadata or {},
            )
            self.db.add(message)

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
        try:
            from engine.main import agent

            conversation = self.get_or_create_conversation(conversation_id)
            self.save_message(
                conversation_id=conversation.id, role="user", content=message
            )

            logger.info(f"Invoking agent for conversation {conversation.id}")

            if stream:
                logger.warning(
                    "Streaming not fully supported, returning complete response"
                )

            agent_response = agent.invoke(
                {"messages": [{"role": "user", "content": message}]}
            )

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
        try:
            from engine.main import agent

            conversation = self.get_or_create_conversation(conversation_id)
            self.save_message(
                conversation_id=conversation.id, role="user", content=message
            )

            logger.info(f"Starting streaming for conversation {conversation.id}")

            yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation.id})}\n\n"

            agent_response = agent.invoke(
                {"messages": [{"role": "user", "content": message}]}
            )

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

            words = response_content.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

            assistant_message = self.save_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response_content,
                metadata={"agent_response": True, "streamed": True},
            )

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_message.id})}\n\n"

            logger.info(f"Streaming completed for conversation {conversation.id}")

        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            error_data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {error_data}\n\n"
