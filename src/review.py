#!/usr/bin/env python3
"""
Review interface for managing temporary database and transferring words to main vocabulary.
"""

from database import (
    get_temp_words, add_word, word_exists, add_tag_to_word, 
    remove_temp_word, clear_temp_session
)

def list_temp_sessions():
    """List all unique session IDs in temporary database."""
    temp_words = get_temp_words()
    sessions = {}
    
    for word_record in temp_words:
        word, lemma, pos, translation, is_regular, session_id, created_at = word_record
        if session_id not in sessions:
            sessions[session_id] = {'count': 0, 'created_at': created_at}
        sessions[session_id]['count'] += 1
    
    return sessions

def display_temp_words(session_id):
    """Display all words in a temporary session."""
    temp_words = get_temp_words(session_id)
    
    if not temp_words:
        print(f"No words found in session '{session_id}'")
        return []
    
    print(f"\nWords in session '{session_id}':")
    print("-" * 60)
    
    for i, word_record in enumerate(temp_words, 1):
        word, lemma, pos, translation, is_regular, sess_id, created_at = word_record
        reg_status = ""
        if pos in ["VERB", "AUX"]:
            reg_status = " (irregular)" if is_regular is False else " (regular)"
        
        print(f"{i:2}. {word} -> {lemma} [{pos}]{reg_status}")
    
    return temp_words

def review_session(session_id):
    """Interactive review of words in a temporary session."""
    temp_words = display_temp_words(session_id)
    
    if not temp_words:
        return
    
    print(f"\nReviewing {len(temp_words)} words from session '{session_id}'")
    print("Commands: (A)dd to main DB, (S)kip, (Q)uit, (D)elete from temp, (C)lear session")
    
    transferred_count = 0
    deleted_count = 0
    
    for word_record in temp_words:
        word, lemma, pos, translation, is_regular, sess_id, created_at = word_record
        
        reg_status = ""
        if pos in ["VERB", "AUX"]:
            reg_status = " (irregular)" if is_regular is False else " (regular)"
        
        print(f"\nWord: {word} -> {lemma} [{pos}]{reg_status}")
        
        # Check if already exists in main database
        if word_exists(lemma):
            print(f"  Note: '{lemma}' already exists in main database")
        
        while True:
            action = input("Action (A/S/Q/D/C): ").strip().upper()
            
            if action == "Q":
                print("Review stopped by user.")
                return transferred_count, deleted_count
            
            elif action == "S":
                break
            
            elif action == "D":
                # Delete from temp database
                if remove_temp_word(word, session_id):
                    print(f"  Removed '{word}' from temp database")
                    deleted_count += 1
                break
            
            elif action == "C":
                # Clear entire session
                if input("Clear entire session? (y/N): ").strip().lower() == 'y':
                    cleared_count = clear_temp_session(session_id)
                    print(f"Cleared session - {cleared_count} words removed")
                    return transferred_count, cleared_count
                break
            
            elif action == "A":
                # Add to main database
                if word_exists(lemma):
                    print(f"  '{lemma}' already exists in main database - skipping")
                    break
                
                # Get translation from user
                translation = input("  Enter translation (or press Enter to skip): ").strip()
                if not translation:
                    translation = None
                
                # Add to main database
                add_word(lemma, pos, is_regular, translation)
                
                # Get tags from user
                tags_input = input("  Enter tags (comma-separated, or press Enter for none): ").strip()
                if tags_input:
                    user_tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
                    for tag in user_tags:
                        add_tag_to_word(lemma, tag)
                
                # Automatically add POS-based tags
                if pos == "NOUN":
                    add_tag_to_word(lemma, "noun")
                elif pos in ["VERB", "AUX"]:
                    add_tag_to_word(lemma, "verb")
                    if is_regular is False:
                        add_tag_to_word(lemma, "irregular")
                
                print(f"  Added '{lemma}' to main database")
                transferred_count += 1
                
                # Remove from temp database
                remove_temp_word(word, session_id)
                break
            
            else:
                print("Invalid action. Please use A, S, Q, D, or C.")
    
    print(f"\nReview complete: {transferred_count} words transferred, {deleted_count} words deleted")
    return transferred_count, deleted_count

def review_interface():
    """Main interface for reviewing temporary database sessions."""
    while True:
        print("\n" + "=" * 50)
        print("VOCAB HARVESTER - REVIEW INTERFACE")
        print("=" * 50)
        
        # List available sessions
        sessions = list_temp_sessions()
        
        if not sessions:
            print("No words in temporary database.")
            return
        
        print("Available sessions:")
        session_list = list(sessions.keys())
        
        for i, session_id in enumerate(session_list, 1):
            session_info = sessions[session_id]
            print(f"{i:2}. {session_id} ({session_info['count']} words) - {session_info['created_at']}")
        
        print("\nOptions:")
        print("1-N. Review session by number")
        print("0. Exit")
        
        try:
            choice = input("\nSelect option: ").strip()
            
            if choice == "0":
                break
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(session_list):
                selected_session = session_list[choice_num - 1]
                review_session(selected_session)
            else:
                print("Invalid selection.")
                
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    review_interface()