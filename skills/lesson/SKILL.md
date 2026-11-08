---
name: lesson
description: Start the web server and open the exercise page for an Episode. Use when the learner types /lesson, or asks to open the page or to do the Word Knowledge Check.
argument-hint: <Series/S01E03>
---

Open the exercise page for the Episode `$ARGUMENTS`.

1. If no Episode is given above, ask the learner which Episode, for example `Dark/S01E03`. Then continue.
2. Turn the Episode into a folder name under the media folder: `<Series>/S<nn>E<nn>`. "Dark S01E03" becomes `Dark/S01E03`.
3. Call the tool `mcp__plugin_german-media-learning_learning__open_page` with that Episode. The tool starts the web server if it does not run yet, and opens the page in the browser on its Check tab.
4. Tell the learner the URL from the tool result. The page runs while this Claude Code session runs.
5. If the tool gives an error, tell the learner the error in one sentence.
