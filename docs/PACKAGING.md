# Packaging the Vocab Harvester UI

This guide shows how to build a standalone executable with PyInstaller.

## Prerequisites
- Python 3.10+ with pip
- spaCy German model installed (`de-core-news-sm`)

## Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download de_core_news_sm
```

## Build command
```bash
pyinstaller --clean vocab_harvester.spec
```

This produces `dist/VocabHarvester/VocabHarvester.exe` (or platform equivalent) without a console window.

## Notes
- The spec bundles:
  - `data/irregular_Verbs.txt`
  - `database/vocab.db` (if present)
  - The `de_core_news_sm` model
- If you need a fresh database, delete `database/vocab.db` before building.
- To reduce size, you can remove `upx` or strip optional packages from `requirements.txt`.

## Runtime tips
- Database files live beside the executable under `database/` by default.
- If the bundled model is missing or outdated, reinstall with `python -m spacy download de_core_news_sm` in the same environment used for packaging, then rebuild.
