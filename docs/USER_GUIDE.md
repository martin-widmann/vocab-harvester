# Vocab Harvester User Guide

## 1. Introduction
Vocab Harvester helps German learners collect, review, and organize vocabulary. Paste German text, process it into a review queue with auto-translation, approve words into your personal vocabulary, and browse everything in one place.

**Who it's for:** German learners who want a lightweight, desktop workflow to turn any text (articles, books, notes) into a structured vocab list.

## 2. Installation
- **System requirements:** Windows 10/11 (primary target), Python 3.10+ if running from source. Linux/macOS may work but are untested.
- **From source:**  
  ```bash
  pip install -r requirements.txt
  python -m spacy download de_core_news_sm
  python src/ui/main.py
  ```
- **Executable (if provided):** Download the packaged build (PyInstaller). No Python needed. Ensure `de_core_news_sm` is bundled; if you see model errors, install it in the packaging environment and rebuild.

## 3. Getting Started
1) Launch the app (`python src/ui/main.py` or the packaged executable).  
2) The interface has three tabs:
   - **Text Processing**: paste text and process into a temporary review queue.
   - **Review Queue**: approve/reject/skip words.
   - **Vocabulary**: browse approved words with filters and search.

## 4. Text Processing Tab
- Paste German text into the large box (placeholder shown initially).  
- Click **Process Text**; the button disables while processing.  
- The app:
  - Cleans the text, tokenizes, lemmatizes (adds der/die/das for nouns), filters known words, auto-translates, and stores unknowns in a session-specific temp database.  
  - Shows session ID, words processed/added/translated, and a success message guiding you to Review Queue.  
- Click **Clear** to reset the input.  
- If the text is empty, you get a friendly error. If nothing was added, you’re told why.  
- Best practices: use well-formed sentences; very noisy text may yield few tokens.

## 5. Review Queue Tab
- Use the Session dropdown to pick a processing session, then **Load Session**.  
- Word details show original, lemma, POS, and translation (or “No translation”).  
- **Difficulty (0-4):** 0 Known, 1 Super Easy, 2 Easy, 3 Medium (default), 4 Hard.  
- **Tags:** optional, comma-separated (e.g., `medical, news`).  
- Actions:
  - **Approve**: moves the lemma to the main vocab with difficulty/tags, removes from temp.
  - **Reject**: removes from temp without adding to vocab.
  - **Skip**: moves to the next word without action.
- Progress label shows “Word X of Y”; when done, you see “Session complete!” and buttons disable.

## 6. Vocabulary Database Tab
- Browse all approved words in a table (Word, POS, Translation, Difficulty, Tags).  
- Search filters by word/translation/tags in real time.  
- Difficulty filter shows only selected levels.  
- Double-click a row to view details in a popup.

## 7. Workflow Examples
- **Complete flow:** Paste text → Process → Review Queue: approve/reject → Vocabulary tab to browse results.  
- **News article:** Paste an article, process, approve key terms with tags like `news, politics`.  
- **Book chapter:** Paste a chapter, process, mark easier known words as 0-1, harder as 3-4, tag `literature, novel`.

## 8. Tips and Best Practices
- Use tags to group domains (`medical`, `legal`, `travel`).  
- Difficulty: 0/1 for known/very easy, 2 for easy, 3 default, 4 for hard/rare.  
- Manage sessions: process smaller chunks for quicker review; refresh sessions in Review Queue if you processed new text.  
- Duplicates: existing vocab is filtered out; temp duplicates per session are ignored.

## 9. Troubleshooting
- **spaCy model not found**: run `python -m spacy download de_core_news_sm` in the same environment used to run/build the app.  
- **App won’t start (packaged)**: ensure the executable isn’t blocked by antivirus; re-run with the bundled files intact.  
- **Database issues**: delete/recreate `database/vocab.db` if corrupted (you’ll lose saved words).  
- **No words processed**: text may be empty or contain no recognizable tokens. Try different text.  
- **Console/terminal pops up**: use the windowed build (`console=False` in PyInstaller spec).

## 10. FAQ
- **How are articles detected?** spaCy gender detection maps to der/die/das.  
- **Can I edit words after approval?** Not in the UI yet; you can edit the database directly if needed.  
- **How to export vocabulary?** Not built-in; export would be a future enhancement.  
- **Other languages?** The pipeline is German-specific (model, article logic); adapting to other languages would require code and model changes.
