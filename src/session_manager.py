"""
Session Management Controller for Batch Processing Workflow (Issue #9)

This module orchestrates the complete batch processing workflow from text input
to temporary storage, coordinating between parser, translation service, and
database operations.

Features:
- Session creation with unique UUIDs
- Batch text processing coordination
- Progress tracking during processing
- Session status monitoring
- Session persistence and resumption
- Error handling and recovery
"""

import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum

# Import existing modules
from parser import process_text_input, clean_text_input
from database import (
    get_pending_words,
    clear_session,
    get_temp_words,
    add_temp_word
)


class SessionStatus(Enum):
    """Enumeration of possible session states."""
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


class ProcessingSession:
    """
    Processing session that orchestrates batch text processing workflow.

    Manages the complete lifecycle of a batch processing session from text input
    through tokenization, lemmatization, translation, and temporary storage.
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize a processing session.

        Args:
            session_id: Optional session ID. If None, generates a new UUID-based ID.
        """
        if session_id is None:
            # Generate unique session ID with timestamp and UUID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            self.session_id = f"session_{timestamp}_{unique_id}"
        else:
            self.session_id = session_id

        self.status = SessionStatus.CREATED
        self.created_at = datetime.now()
        self.completed_at = None
        self.error_message = None

        # Processing statistics
        self.total_words_processed = 0
        self.words_added = 0
        self.words_translated = 0
        self.words_failed = 0

        # Progress tracking
        self.current_word = 0
        self.total_words = 0

        # Text input
        self.original_text = ""
        self.cleaned_text = ""

    def start_session(self, text_input: str) -> Dict[str, any]:
        """
        Start a processing session with the given text input.

        Coordinates the entire batch workflow:
        1. Text cleaning and validation
        2. Tokenization and lemmatization
        3. Translation service calls
        4. Temporary database storage
        5. Progress tracking

        Args:
            text_input: Raw German text to process

        Returns:
            Dictionary containing session results and status
        """
        try:
            self.status = SessionStatus.PROCESSING
            self.original_text = text_input

            # Validate text input
            self.cleaned_text = clean_text_input(text_input)
            if not self.cleaned_text:
                self.status = SessionStatus.FAILED
                self.error_message = "Empty or invalid text input"
                return self._build_result(success=False)

            # Process text through the pipeline
            # This coordinates: parser → translation → temp database
            processing_result = process_text_input(self.cleaned_text, self.session_id)

            if processing_result is None:
                self.status = SessionStatus.FAILED
                self.error_message = "Text processing failed"
                return self._build_result(success=False)

            # Update session statistics
            self.total_words_processed = processing_result.get('words_processed', 0)
            self.words_added = processing_result.get('words_added', 0)
            self.words_translated = processing_result.get('words_translated', 0)

            # Mark session as completed or pending review
            if self.words_added > 0:
                self.status = SessionStatus.PENDING_REVIEW
            else:
                self.status = SessionStatus.COMPLETED

            self.completed_at = datetime.now()

            # Save session state to disk for persistence
            self._save_session_state()

            return self._build_result(success=True)

        except Exception as e:
            self.status = SessionStatus.FAILED
            self.error_message = f"Unexpected error: {str(e)}"
            self.completed_at = datetime.now()
            return self._build_result(success=False)

    def get_session_status(self) -> Dict[str, any]:
        """
        Get current status and progress of the session.

        Returns:
            Dictionary containing session status, progress, and statistics
        """
        # Get current pending words count
        pending_words = get_pending_words(self.session_id)
        pending_count = len(pending_words)

        # Calculate processing duration
        if self.completed_at:
            duration = (self.completed_at - self.created_at).total_seconds()
        else:
            duration = (datetime.now() - self.created_at).total_seconds()

        return {
            'session_id': self.session_id,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': round(duration, 2),
            'statistics': {
                'total_words_processed': self.total_words_processed,
                'words_added': self.words_added,
                'words_translated': self.words_translated,
                'words_failed': self.words_failed,
                'words_pending_review': pending_count
            },
            'error_message': self.error_message,
            'text_preview': self.cleaned_text[:100] + "..." if len(self.cleaned_text) > 100 else self.cleaned_text
        }

    def get_session_words(self) -> List[Dict[str, any]]:
        """
        Retrieve all pending words for this session.

        Returns:
            List of word dictionaries containing word data for review
        """
        try:
            # Get words from temporary database for this session
            temp_words = get_temp_words(self.session_id)

            # Format words into structured dictionaries
            formatted_words = []
            for word_tuple in temp_words:
                word, lemma, pos, translation, is_regular, session_id, created_at = word_tuple

                formatted_words.append({
                    'word': word,
                    'lemma': lemma,
                    'pos': pos,
                    'translation': translation,
                    'is_regular': is_regular,
                    'created_at': created_at
                })

            return formatted_words

        except Exception as e:
            print(f"Error retrieving session words: {e}")
            return []

    def get_progress_string(self) -> str:
        """
        Get a formatted progress string for display.

        Returns:
            Formatted string like "Processing word 15 of 23"
        """
        if self.status == SessionStatus.PROCESSING and self.total_words > 0:
            return f"Processing word {self.current_word} of {self.total_words}"
        elif self.status == SessionStatus.COMPLETED:
            return f"Completed: {self.words_added} words processed"
        elif self.status == SessionStatus.PENDING_REVIEW:
            pending = len(get_pending_words(self.session_id))
            return f"Pending review: {pending} words awaiting approval"
        elif self.status == SessionStatus.FAILED:
            return f"Failed: {self.error_message}"
        else:
            return "Session initialized"

    def clear_session_data(self) -> int:
        """
        Clear all words from this session's temporary storage.

        Returns:
            Number of words removed
        """
        try:
            count = clear_session(self.session_id)

            # Update status
            if self.status == SessionStatus.PENDING_REVIEW:
                self.status = SessionStatus.COMPLETED

            return count

        except Exception as e:
            print(f"Error clearing session: {e}")
            return 0

    def _build_result(self, success: bool) -> Dict[str, any]:
        """
        Build a standardized result dictionary.

        Args:
            success: Whether the operation was successful

        Returns:
            Dictionary containing operation results
        """
        return {
            'success': success,
            'session_id': self.session_id,
            'status': self.status.value,
            'statistics': {
                'total_words_processed': self.total_words_processed,
                'words_added': self.words_added,
                'words_translated': self.words_translated,
                'words_failed': self.words_failed
            },
            'error_message': self.error_message
        }

    def _save_session_state(self):
        """
        Save session state to disk for persistence.

        Creates a JSON file in the sessions directory containing all session data.
        """
        try:
            # Create sessions directory if it doesn't exist
            sessions_dir = "C:/Users/marti/Projects-2025/vocab-harvester/sessions"
            os.makedirs(sessions_dir, exist_ok=True)

            # Build session data
            session_data = {
                'session_id': self.session_id,
                'status': self.status.value,
                'created_at': self.created_at.isoformat(),
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'error_message': self.error_message,
                'statistics': {
                    'total_words_processed': self.total_words_processed,
                    'words_added': self.words_added,
                    'words_translated': self.words_translated,
                    'words_failed': self.words_failed
                },
                'text_preview': self.cleaned_text[:200] if self.cleaned_text else ""
            }

            # Save to JSON file
            filename = os.path.join(sessions_dir, f"{self.session_id}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Warning: Could not save session state: {e}")

    def _load_session_state(self):
        """
        Load session state from disk.

        Restores a previously saved session from its JSON file.
        """
        try:
            sessions_dir = "C:/Users/marti/Projects-2025/vocab-harvester/sessions"
            filename = os.path.join(sessions_dir, f"{self.session_id}.json")

            if not os.path.exists(filename):
                return False

            with open(filename, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Restore session state
            self.status = SessionStatus(session_data['status'])
            self.created_at = datetime.fromisoformat(session_data['created_at'])
            self.completed_at = datetime.fromisoformat(session_data['completed_at']) if session_data['completed_at'] else None
            self.error_message = session_data['error_message']

            stats = session_data['statistics']
            self.total_words_processed = stats['total_words_processed']
            self.words_added = stats['words_added']
            self.words_translated = stats['words_translated']
            self.words_failed = stats['words_failed']

            self.cleaned_text = session_data.get('text_preview', '')

            return True

        except Exception as e:
            print(f"Warning: Could not load session state: {e}")
            return False


class SessionManager:
    """
    Manager for handling multiple processing sessions.

    Provides high-level coordination for creating, tracking, and managing
    multiple concurrent processing sessions.
    """

    def __init__(self):
        """Initialize the session manager."""
        self.sessions: Dict[str, ProcessingSession] = {}
        self._load_all_sessions()

    def create_session(self, text_input: str) -> ProcessingSession:
        """
        Create and start a new processing session.

        Args:
            text_input: Raw German text to process

        Returns:
            ProcessingSession instance
        """
        session = ProcessingSession()
        self.sessions[session.session_id] = session

        # Start processing the text
        result = session.start_session(text_input)

        return session

    def get_session(self, session_id: str) -> Optional[ProcessingSession]:
        """
        Retrieve an existing session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            ProcessingSession instance or None if not found
        """
        # Check in-memory sessions first
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try to load from disk
        session = ProcessingSession(session_id)
        if session._load_session_state():
            self.sessions[session_id] = session
            return session

        return None

    def list_sessions(self, status_filter: Optional[SessionStatus] = None) -> List[Dict[str, any]]:
        """
        List all sessions, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of session summary dictionaries
        """
        sessions_list = []

        for session in self.sessions.values():
            if status_filter is None or session.status == status_filter:
                sessions_list.append({
                    'session_id': session.session_id,
                    'status': session.status.value,
                    'created_at': session.created_at.isoformat(),
                    'words_added': session.words_added,
                    'pending_words': len(get_pending_words(session.session_id))
                })

        # Sort by creation time (most recent first)
        sessions_list.sort(key=lambda x: x['created_at'], reverse=True)

        return sessions_list

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its data.

        Args:
            session_id: The session ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear session data from database
            clear_session(session_id)

            # Remove session file
            sessions_dir = "C:/Users/marti/Projects-2025/vocab-harvester/sessions"
            filename = os.path.join(sessions_dir, f"{session_id}.json")
            if os.path.exists(filename):
                os.remove(filename)

            # Remove from in-memory sessions
            if session_id in self.sessions:
                del self.sessions[session_id]

            return True

        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def _load_all_sessions(self):
        """
        Load all saved sessions from disk.

        Scans the sessions directory and loads all session files.
        """
        try:
            sessions_dir = "C:/Users/marti/Projects-2025/vocab-harvester/sessions"

            if not os.path.exists(sessions_dir):
                return

            for filename in os.listdir(sessions_dir):
                if filename.endswith('.json'):
                    session_id = filename[:-5]  # Remove .json extension
                    session = ProcessingSession(session_id)
                    if session._load_session_state():
                        self.sessions[session_id] = session

        except Exception as e:
            print(f"Warning: Could not load sessions: {e}")


# Convenience functions for easy usage

def start_processing_session(text_input: str) -> Tuple[str, Dict[str, any]]:
    """
    Convenience function to start a new processing session.

    Args:
        text_input: Raw German text to process

    Returns:
        Tuple of (session_id, result_dict)
    """
    manager = SessionManager()
    session = manager.create_session(text_input)
    result = session.get_session_status()
    return session.session_id, result


def get_session_info(session_id: str) -> Optional[Dict[str, any]]:
    """
    Convenience function to get session information.

    Args:
        session_id: The session ID to query

    Returns:
        Session status dictionary or None if not found
    """
    manager = SessionManager()
    session = manager.get_session(session_id)
    if session:
        return session.get_session_status()
    return None


def get_session_words_for_review(session_id: str) -> List[Dict[str, any]]:
    """
    Convenience function to get words from a session for review.

    Args:
        session_id: The session ID to query

    Returns:
        List of word dictionaries
    """
    manager = SessionManager()
    session = manager.get_session(session_id)
    if session:
        return session.get_session_words()
    return []


def clear_completed_sessions() -> int:
    """
    Clear all completed sessions that have no pending words.

    Returns:
        Number of sessions cleared
    """
    manager = SessionManager()
    cleared_count = 0

    completed_sessions = manager.list_sessions(status_filter=SessionStatus.COMPLETED)

    for session_info in completed_sessions:
        if session_info['pending_words'] == 0:
            if manager.delete_session(session_info['session_id']):
                cleared_count += 1

    return cleared_count
