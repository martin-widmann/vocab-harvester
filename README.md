# VocabHarvest - Technical Specification for Development

## Project Overview

VocabHarvest is a desktop vocabulary learning application built in Python that processes German text to extract unknown words, fetches English translations, and manages a personal vocabulary database.

**Core Value Proposition**: Transform German text reading into vocabulary acquisition by identifying unknown words, providing translations, and building a personal vocabulary database.

## System Architecture

### Technology Stack

- **Language**: Python 3.8+
- **GUI Framework**: tkinter (built-in) or PyQt
- **Database**: SQLite3
- **NLP Processing**: spaCy with German language model
- **Translation API**: Wiktionary API (primary)
- **HTTP Client**: requests library

### Database Design

#### Primary Vocabulary Database

Contains the main vocabulary storage with word information including unique identifiers, German words with their lemmatized forms, English translations, part-of-speech tags, first encounter dates, and frequency rankings. Implements a flexible tagging system through a separate tags relationship that allows multiple tags per word and shared tags across multiple words using foreign key relationships.

#### Temporary Processing Database

Serves as temporary storage for words awaiting user decision during processing sessions. Mirrors the vocabulary structure but includes additional fields for custom tags and creation timestamps. Prevents duplicate entries of the same word with identical part-of-speech tags and persists between application sessions to allow interrupted workflow resumption.

## Backend Implementation Requirements

### Text Processing Pipeline (Parsing) Module

**Purpose**: Extract and process German words from input text
**Dependencies**: spaCy German model

**Core Functionality**:
Processes German text input using spaCy natural language processing to tokenize text into individual words, extract lemmatized forms and part-of-speech tags, filter out punctuation and non-meaningful tokens, and return structured data containing word information. Additionally filters processed words against existing vocabulary database to identify unknown words and handles text preprocessing including normalization and cleaning.

### Translation Service Module

**Purpose**: Fetch English translations for German words
**Dependencies**: requests library for HTTP communication

**Core Functionality**:
Interfaces with Wiktionary API to retrieve German-English translations, handles API authentication and response parsing, implements error handling for network connectivity issues and API timeouts, provides fallback mechanisms for failed translation requests, supports batch translation operations for efficiency, and maintains translation quality by leveraging part-of-speech context.

### Database Manager Module

**Purpose**: Handle all SQLite operations for both vocabulary and temporary databases
**Dependencies**: sqlite3 for database operations

**Core Functionality**:
Initializes and maintains schema for both main and temporary databases, manages database connections and transactions, performs operations on vocabulary and pending words tables, handles word insertion and deletion in both databases, implements word lookup and filtering against existing vocabulary, manages tag relationships and associations, supports data migration between temporary and permanent storage, and provides database integrity checks and maintenance operations.

## Frontend Implementation Requirements

### Main Application Structure

**GUI Framework**: tkinter with ttk widgets for modern appearance

### Window Layout Specification

The main application window features a tabbed interface with the primary "Main" tab always visible. The layout consists of three main sections: a text input area at the top for pasting German text with process and clear buttons, a pending words section in the middle displaying unknown vocabulary in a table format with individual action buttons for each word, and a status bar at the bottom showing connectivity, database status, and pending word count. The pending words table displays columns for German word, part-of-speech, English translation, custom tags input field, and action buttons (Add/Discard). Additional tabs for vocabulary browsing and statistics are available but not part of the initial implementation.

### GUI Component Requirements

#### Text Input Section

Multi-line text widget with scrollbar capabilities for German text input. Features include word count display, clear functionality, and validation to ensure non-empty text before processing begins.

#### Pending Words Table

Table widget displaying pending vocabulary with sortable columns for German words, part-of-speech tags, English translations, custom tags, and individual action controls. Supports both individual word actions and batch operations for multiple words simultaneously.

#### Action Buttons

Interface controls for moving words from temporary to permanent storage with optional tagging, removing words from pending lists, triggering the complete text processing pipeline, and resetting the text input area.

#### Status Bar

Visual indicators showing internet connectivity status, database connection status, processing progress during operations, and count of words awaiting user decision.

## Application Workflow

### Primary User Journey

User pastes German text into input area and triggers processing. The backend pipeline extracts words using spaCy, filters against known vocabulary, fetches translations from Wiktionary, and stores results in temporary database. Results populate the pending words table in the GUI where users choose to add words with optional tags or discard them. Accepted words move to permanent storage while discarded words are deleted from temporary storage.

### Error Handling Requirements

The application handles scenarios including no internet connectivity by disabling processing and showing warning messages, API failures through error dialogs with retry options, database errors with graceful degradation and user notifications, and invalid input through validation with helpful error messages.

### Performance Requirements

The system implements asynchronous operations to prevent GUI freezing during API calls, efficient batch processing for large word lists, database optimization using prepared statements and transactions, and proper memory management with resource cleanup after processing.

## File Structure for Development

The project follows a standard Python package structure with source code organized in a src directory containing the main application modules. Test files are separated into their own directory with corresponding test modules. Data files including both vocabulary databases are stored in a dedicated data directory. The project includes standard Python project files for dependencies and documentation.

## Development Priorities

1. **Phase 1**: Backend pipeline (text processing, translation, database)
2. **Phase 2**: Basic GUI (text input, display results, basic actions)
3. **Phase 3**: Enhanced UI (batch operations, better styling, error handling)
4. **Phase 4**: Optimization (performance improvements, caching, advanced features)
