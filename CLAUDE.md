# Claude Code Session Log

## Session 2025-09-01: Text Processing Pipeline & Database Restructure

### ✅ COMPLETED - Core Pipeline Implementation:

**1. Text Processing Pipeline Built** (`src/parser.py`):
- ✅ Changed from frequency list processing to text input processing
- ✅ Implemented full spaCy tokenization (handles punctuation, contractions properly)
- ✅ Complete pipeline: `Text Input → Tokenization → Lemmatization → Filter Known Words → Database Storage`
- ✅ Interactive user prompts for each new word with manual tagging

**2. Database Schema Restructured** (`src/database.py`):
- ✅ **Removed**: `freq_rank` and `encounter_date` columns
- ✅ **Simplified vocab table**: `word (PK), pos, is_regular`
- ✅ **Added flexible tagging system**: 
  - `tags` table: `tag_id, tag_name, description`
  - `word_tags` table: many-to-many relationship
  - Full CRUD operations for tag management

**3. Manual Tagging System**:
- ✅ **User-controlled**: Each word prompts "Add (A), Skip (S), Quit (Q)"
- ✅ **Per-word tagging**: "Enter tags (comma-separated, or press Enter for none)"
- ✅ **No automatic bulk tagging** - prevents irrelevant tags on common words
- ✅ **Multiple tags per word** supported (e.g., "medical,technical,difficult")

**4. Project Organization**:
- ✅ **Test files moved**: `src/test_*.py` → `tests/` (best practice)
- ✅ **Import paths fixed**: Added `sys.path.append()` for tests to access src modules
- ✅ **Main entry point**: `src/main.py` with interactive interface

### 🎯 CURRENT STATE:
- **Core functionality**: Text processing pipeline fully working
- **Database**: Clean schema with flexible tagging system
- **Entry point**: Run `python src/main.py` for interactive text processing
- **Tests**: Located in `tests/` directory, all imports working

### 📋 NEXT SESSION PRIORITIES:
1. **Test the complete interactive workflow** with real German text
2. **Consider adding**: Word export/review functionality
3. **Potential**: Integration with frequency lists if needed
4. **Future**: Flashcard generation or spaced repetition features

### 🔧 KEY FILES:
- **`src/main.py`**: Interactive entry point
- **`src/parser.py`**: Complete text processing pipeline
- **`src/database.py`**: Database operations + tagging system
- **`tests/test_*.py`**: Test suite for verification

### ⚙️ TECHNICAL NOTES:
- **spaCy model**: Using `de_core_news_sm` for German
- **Database**: SQLite with proper foreign key constraints
- **Text processing**: Handles German umlauts and special characters
- **Tagging approach**: Manual per-word (user decides relevance)

### 🐛 KNOWN ISSUES:
- Windows console Unicode encoding issues with emoji characters in demo files (non-critical)

---

## Previous Session (2025-08-31): Repository Setup

### Repository Details:
- **Repository**: `git@github.com:martin-widmann/vocab-harvester.git`  
- **Working Directory**: `C:\Users\marti\Projects-2025\vocab-harvester`
- **Status**: Repository renamed and directory structure established

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for `martin-widmann/vocab-harvester`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels, each label string equal to its role name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
