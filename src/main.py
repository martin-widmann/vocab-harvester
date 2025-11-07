#!/usr/bin/env python3
"""
VocabHarvester - Main entry point for batch processing workflow

This is the main application entry point that uses the session management
controller for coordinating the complete batch processing workflow.

Updated for Issue #10: Integrated with session management controller
"""

from session_manager import (
    SessionManager,
    SessionStatus,
    start_processing_session,
    get_session_info
)
from database import get_pending_words, approve_word, reject_word
from review import review_interface


def display_session_summary(session_info):
    """Display a summary of session information."""
    print("\n" + "=" * 60)
    print(f"Session: {session_info['session_id']}")
    print("=" * 60)
    print(f"Status: {session_info['status']}")
    print(f"Duration: {session_info['duration_seconds']}s")

    stats = session_info['statistics']
    print("\nStatistics:")
    print(f"  Total words processed: {stats['total_words_processed']}")
    print(f"  Words added to temp DB: {stats['words_added']}")
    print(f"  Words translated: {stats['words_translated']}")
    print(f"  Words pending review: {stats['words_pending_review']}")

    if session_info['error_message']:
        print(f"\nError: {session_info['error_message']}")

    if session_info['text_preview']:
        print(f"\nText preview: {session_info['text_preview']}")


def start_new_session():
    """Start a new batch processing session."""
    print("\n" + "=" * 60)
    print("START NEW BATCH PROCESSING SESSION")
    print("=" * 60)
    print("\nEnter German text to process (press Enter twice when done):")

    lines = []
    while True:
        try:
            line = input()
            if line == "":
                if lines:  # If we have content, stop
                    break
                else:  # If no content yet, continue
                    continue
            lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)

    if not text.strip():
        print("\nNo text entered. Cancelling.")
        return None

    print(f"\nProcessing text ({len(text)} characters)...")
    print("This may take a moment for translation lookups...")

    try:
        session_id, result = start_processing_session(text)

        print("\n" + "=" * 60)
        print("SESSION CREATED SUCCESSFULLY")
        print("=" * 60)

        # Display session info
        session_info = get_session_info(session_id)
        if session_info:
            display_session_summary(session_info)

        return session_id

    except Exception as e:
        print(f"\nError creating session: {e}")
        return None


def view_session_status():
    """View status of existing sessions."""
    print("\n" + "=" * 60)
    print("VIEW SESSION STATUS")
    print("=" * 60)

    manager = SessionManager()
    sessions_list = manager.list_sessions()

    if not sessions_list:
        print("\nNo sessions found.")
        return

    print(f"\nFound {len(sessions_list)} session(s):\n")

    for i, session_info in enumerate(sessions_list, 1):
        print(f"{i}. Session: {session_info['session_id'][:30]}...")
        print(f"   Status: {session_info['status']}")
        print(f"   Words added: {session_info['words_added']}")
        print(f"   Pending review: {session_info['pending_words']}")
        print(f"   Created: {session_info['created_at']}")
        print()

    # Ask if user wants to view details of a specific session
    try:
        choice = input("Enter session number for details (or press Enter to return): ").strip()
        if choice:
            choice_num = int(choice)
            if 1 <= choice_num <= len(sessions_list):
                selected = sessions_list[choice_num - 1]
                session_id = selected['session_id']

                # Get full session info
                full_info = get_session_info(session_id)
                if full_info:
                    display_session_summary(full_info)
            else:
                print("Invalid selection.")
    except ValueError:
        print("Invalid input.")
    except KeyboardInterrupt:
        print("\nCancelled.")


def view_pending_sessions():
    """View and manage sessions with pending words."""
    print("\n" + "=" * 60)
    print("PENDING SESSIONS (Words Awaiting Review)")
    print("=" * 60)

    manager = SessionManager()
    pending_sessions = manager.list_sessions(status_filter=SessionStatus.PENDING_REVIEW)

    if not pending_sessions:
        print("\nNo sessions with pending words.")
        return

    print(f"\nFound {len(pending_sessions)} session(s) with pending words:\n")

    for i, session_info in enumerate(pending_sessions, 1):
        print(f"{i}. Session: {session_info['session_id'][:40]}...")
        print(f"   Words pending: {session_info['pending_words']}")
        print(f"   Created: {session_info['created_at']}")
        print()

    # Ask if user wants to review a specific session
    try:
        choice = input("Enter session number to review (or press Enter to return): ").strip()
        if choice:
            choice_num = int(choice)
            if 1 <= choice_num <= len(pending_sessions):
                selected = pending_sessions[choice_num - 1]
                session_id = selected['session_id']

                # Quick review interface for this session
                quick_review_session(session_id)
            else:
                print("Invalid selection.")
    except ValueError:
        print("Invalid input.")
    except KeyboardInterrupt:
        print("\nCancelled.")


def quick_review_session(session_id):
    """Quick review interface for a specific session."""
    print("\n" + "=" * 60)
    print(f"QUICK REVIEW - Session: {session_id[:40]}...")
    print("=" * 60)

    pending = get_pending_words(session_id)

    if not pending:
        print("\nNo pending words in this session.")
        return

    print(f"\nFound {len(pending)} pending word(s):\n")

    for i, word_data in enumerate(pending, 1):
        word, lemma, pos, translation, is_regular, sess_id, created_at = word_data

        reg_status = ""
        if pos in ["VERB", "AUX"]:
            reg_status = " (irregular)" if is_regular is False else " (regular)"

        trans_str = f" -> {translation}" if translation else " (no translation)"

        print(f"{i:2}. {lemma} [{pos}]{reg_status}{trans_str}")

    print("\nOptions:")
    print("  (A)pprove all words")
    print("  (R)eject all words")
    print("  (D)etailed review (use full review interface)")
    print("  (B)ack to main menu")

    choice = input("\nSelect option: ").strip().upper()

    if choice == "A":
        print("\nApproving all words...")
        approved = 0
        for word_data in pending:
            word, lemma, pos, translation, is_regular, sess_id, created_at = word_data
            if approve_word(lemma, session_id):
                approved += 1
        print(f"Approved {approved} word(s).")

    elif choice == "R":
        print("\nRejecting all words...")
        rejected = 0
        for word_data in pending:
            word, lemma, pos, translation, is_regular, sess_id, created_at = word_data
            if reject_word(lemma, session_id):
                rejected += 1
        print(f"Rejected {rejected} word(s).")

    elif choice == "D":
        print("\nOpening full review interface...")
        review_interface()

    else:
        print("Returning to main menu.")


def manage_sessions():
    """Session management interface."""
    print("\n" + "=" * 60)
    print("SESSION MANAGEMENT")
    print("=" * 60)

    manager = SessionManager()
    all_sessions = manager.list_sessions()

    if not all_sessions:
        print("\nNo sessions found.")
        return

    print(f"\nFound {len(all_sessions)} session(s):\n")

    for i, session_info in enumerate(all_sessions, 1):
        print(f"{i}. {session_info['session_id'][:40]}...")
        print(f"   Status: {session_info['status']}, Pending: {session_info['pending_words']}")

    print("\nOptions:")
    print("  (D)elete session by number")
    print("  (C)lean completed sessions (no pending words)")
    print("  (B)ack to main menu")

    choice = input("\nSelect option: ").strip().upper()

    if choice == "D":
        try:
            num = int(input("Enter session number to delete: ").strip())
            if 1 <= num <= len(all_sessions):
                session_id = all_sessions[num - 1]['session_id']
                confirm = input(f"Delete session {session_id[:40]}...? (y/N): ").strip().lower()
                if confirm == 'y':
                    if manager.delete_session(session_id):
                        print("Session deleted.")
                    else:
                        print("Error deleting session.")
                else:
                    print("Cancelled.")
            else:
                print("Invalid session number.")
        except ValueError:
            print("Invalid input.")

    elif choice == "C":
        from session_manager import clear_completed_sessions
        cleared = clear_completed_sessions()
        print(f"Cleaned {cleared} completed session(s).")

    else:
        print("Returning to main menu.")


def display_main_menu():
    """Display the main menu options."""
    print("\n" + "=" * 60)
    print("VOCAB HARVESTER - BATCH PROCESSING WORKFLOW")
    print("=" * 60)
    print("\nMain Menu:")
    print("  1. Start new batch processing session")
    print("  2. View session status")
    print("  3. Review pending words")
    print("  4. Full review interface (classic)")
    print("  5. Manage sessions")
    print("  6. Exit")
    print()


def main():
    """Main application entry point with session management integration."""
    print("\n" + "=" * 60)
    print("VOCAB HARVESTER")
    print("German Vocabulary Learning - Batch Processing System")
    print("=" * 60)
    print("\nWelcome to VocabHarvester!")
    print("This application helps you extract and learn German vocabulary.")
    print("\nFeatures:")
    print("  - Batch text processing with automatic translation")
    print("  - Session management for organized workflow")
    print("  - Word review and approval system")
    print("  - Integration with Wiktionary for translations")

    while True:
        try:
            display_main_menu()
            choice = input("Select option (1-6): ").strip()

            if choice == "1":
                start_new_session()

            elif choice == "2":
                view_session_status()

            elif choice == "3":
                view_pending_sessions()

            elif choice == "4":
                print("\nOpening full review interface...")
                review_interface()

            elif choice == "5":
                manage_sessions()

            elif choice == "6":
                print("\n" + "=" * 60)
                print("Thank you for using VocabHarvester!")
                print("=" * 60)
                break

            else:
                print("\nInvalid option. Please choose 1-6.")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            print("Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Returning to main menu...")


if __name__ == "__main__":
    main()
