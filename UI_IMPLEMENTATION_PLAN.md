# Vocab Harvester UI Implementation Plan

## Overview
Build a simple Tkinter-based desktop UI with 3 tabs to interact with the existing backend functionality.

**Target:** Executable application for Windows/Linux/Mac
**Technology:** Python Tkinter + PyInstaller
**Design Principle:** Simple, functional, minimal - use only existing backend functions

---

## Phase 1: Backend Preparation

### 1.1 Add Missing Database Functions
**File:** `src/database.py`

**New Functions Needed:**
1. `get_all_words(filters=None, search_term=None)` → List all vocabulary
   - Returns: `[(word, pos, is_regular, translation, difficulty), ...]`
   - Optional: Filter by difficulty, search by word/translation
   - ORDER BY word ASC

2. `get_all_sessions()` → List all processing sessions
   - Returns: `[(session_id, word_count, created_at), ...]`
   - Query temp_vocab table grouped by session_id
   - ORDER BY created_at DESC

3. `get_session_stats(session_id)` → Get statistics for a session
   - Returns: `{total: int, pending: int, approved: int}`
   - Count words in temp_vocab for that session

4. `get_word_count()` → Total words in main vocabulary
   - Returns: int
   - Simple COUNT(*) query

**Testing:** Create `tests/test_database_queries.py` to validate these functions

---

## Phase 2: UI Application Structure

### 2.1 Create Main Application File
**File:** `src/ui/app.py`

**Structure:**
```python
class VocabHarvesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vocab Harvester")
        self.root.geometry("900x600")

        # Create tab container
        self.notebook = ttk.Notebook(root)

        # Initialize tabs
        self.tab1 = TextProcessingTab(self.notebook)
        self.tab2 = VocabularyDatabaseTab(self.notebook)
        self.tab3 = ReviewQueueTab(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.tab1.frame, text="Process Text")
        self.notebook.add(self.tab2.frame, text="Vocabulary")
        self.notebook.add(self.tab3.frame, text="Review Queue")

        self.notebook.pack(expand=True, fill='both')

    def run(self):
        self.root.mainloop()
```

### 2.2 Create Entry Point
**File:** `src/ui/main.py`

```python
import tkinter as tk
from app import VocabHarvesterApp

if __name__ == "__main__":
    root = tk.Tk()
    app = VocabHarvesterApp(root)
    app.run()
```

---

## Phase 3: Tab 1 - Text Processing

### 3.1 Create Text Processing Tab
**File:** `src/ui/tabs/text_processing_tab.py`

**UI Elements:**
- Large Text widget (scrollable, 500px height)
- "Process Text" Button (primary action)
- Results Frame (initially hidden):
  - Session ID label
  - Words processed count
  - Words added count
  - Auto-translated count
- Clear button

**Backend Integration:**
- Import: `from parser import process_text_input`
- On button click: Call `process_text_input(text_content)`
- Display results in results frame
- Store session_id for later use

**Logic Flow:**
1. User pastes text
2. Click "Process Text"
3. Call backend `process_text_input()`
4. Show results
5. Notify user to go to "Review Queue" tab

---

## Phase 4: Tab 2 - Vocabulary Database

### 4.1 Create Vocabulary Database Tab
**File:** `src/ui/tabs/vocabulary_tab.py`

**UI Elements:**
- Search bar (Entry widget) at top
- Filter by difficulty dropdown (0-4, "All")
- Treeview widget (table) with columns:
  - Word (200px width)
  - POS (80px)
  - Translation (200px)
  - Difficulty (80px)
  - Tags (150px)
- Status bar at bottom: "Total words: XXX"
- Refresh button

**Backend Integration:**
- Import: `from database import get_all_words, get_word_tags, get_word_count`
- On load: Call `get_all_words()` and populate table
- On search: Filter table rows
- On difficulty filter: Call `get_all_words(filters={'difficulty': X})`

**Features:**
- Click on row to show full details (optional popup)
- Search filters table in real-time
- Auto-refresh when switching to tab

---

## Phase 5: Tab 3 - Review Queue

### 5.1 Create Review Queue Tab
**File:** `src/ui/tabs/review_queue_tab.py`

**UI Elements:**
- **Top Section:**
  - Session dropdown (Combobox)
  - Load Session button
  - Progress label: "Word 5 of 23"

- **Middle Section (Word Display):**
  - Original form: Label
  - Lemma: Label (larger font)
  - POS: Label
  - Translation: Label
  - Frame with word details

- **Bottom Section (Actions):**
  - Difficulty frame: 5 buttons (0=Known, 1=SuperEasy, 2=Easy, 3=Medium, 4=Hard)
  - Tags entry field (optional)
  - Action buttons:
    - "Approve" (green) - approves with selected difficulty
    - "Reject" (red) - skips word
    - "Next" (gray) - skip without rejecting

**Backend Integration:**
- Import: `from database import get_all_sessions, get_pending_words, approve_word, reject_word`
- On load: Populate session dropdown with `get_all_sessions()`
- On "Load Session": Get words with `get_pending_words(session_id)`
- On "Approve": Call `approve_word(lemma, session_id, difficulty, tags)`
- On "Reject": Call `reject_word(lemma, session_id)`

**Logic Flow:**
1. User selects session from dropdown
2. Click "Load Session"
3. Display first word
4. User clicks difficulty + "Approve" or "Reject"
5. Move to next word
6. When done: Show "Session complete!" message

**State Management:**
- Track current word index
- Track selected difficulty
- Disable buttons when no session loaded

---

## Phase 6: Testing & Polish

### 6.1 Integration Testing
**File:** `tests/test_ui_integration.py`

**Tests:**
- Test text processing workflow
- Test session loading
- Test word approval/rejection
- Test database queries

### 6.2 Error Handling
- Handle empty text input
- Handle no sessions available
- Handle database errors
- Show user-friendly error messages (messagebox)

### 6.3 UI Polish
- Add tooltips to buttons
- Consistent padding/margins
- Keyboard shortcuts (Enter to submit, etc.)
- Disable buttons during processing (prevent double-click)

---

## Phase 7: Packaging & Distribution

### 7.1 Create Executable
**Tool:** PyInstaller

**Steps:**
1. Create `requirements.txt` with dependencies
2. Create PyInstaller spec file
3. Test executable on target OS
4. Handle spaCy model bundling (may need to include separately)

**Command:**
```bash
pyinstaller --onefile --windowed --name VocabHarvester src/ui/main.py
```

### 7.2 Documentation
**File:** `docs/USER_GUIDE.md`

**Contents:**
- Installation instructions
- How to use each tab
- Troubleshooting
- Screenshots

---

## Implementation Order (Priority)

1. **Phase 1** - Backend functions (foundation)
2. **Phase 2** - Application structure (framework)
3. **Phase 3** - Tab 1: Text Processing (most important user entry point)
4. **Phase 5** - Tab 3: Review Queue (core workflow)
5. **Phase 4** - Tab 2: Vocabulary Database (reference/viewing)
6. **Phase 6** - Testing & polish
7. **Phase 7** - Packaging

---

## Technical Decisions

### Why Tkinter?
- ✅ Built-in (no extra dependencies)
- ✅ Cross-platform
- ✅ Easy to package with PyInstaller
- ✅ Good enough for simple CRUD interfaces
- ❌ Not beautiful, but functional

### File Structure
```
src/
  ui/
    __init__.py
    main.py          # Entry point
    app.py           # Main application class
    tabs/
      __init__.py
      text_processing_tab.py
      vocabulary_tab.py
      review_queue_tab.py
  parser.py          # Existing
  database.py        # Existing + new functions
  translation.py     # Existing
```

### Dependencies
- Python 3.8+
- tkinter (built-in)
- spacy (already required)
- sqlite3 (built-in)
- (Optional) ttkthemes for better styling

---

## Success Criteria

✅ User can paste text and process it into temp database
✅ User can review and approve/reject words from temp database
✅ User can view all vocabulary in main database
✅ Application can be packaged as standalone executable
✅ No crashes on normal usage
✅ All existing backend functions work correctly

---

## Future Enhancements (Not in Initial Scope)

- Export vocabulary to CSV/Anki
- Edit existing words in database
- Bulk operations (approve all, reject all)
- Statistics dashboard
- Dark mode
- Custom themes
- Flashcard mode
