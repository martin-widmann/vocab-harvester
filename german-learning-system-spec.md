# German Media Learning System — Spec

Oct 28, 2026 · Martin Widmann

The terms in this spec are defined in [GLOSSARY.md](GLOSSARY.md).

## Purpose and goals

This system teaches you German from German films and series. You use it each day. An AI agent runs it from your own files.

- **Goal:** learn standard German grammar and vocab, so it stays in long-term memory. Over time, the vocab database becomes a true record of the words you know.
- **Your level:** B2.
- **Source:** German series and films. You download each episode as a video file, together with its German subtitles. You watch it in mpv.
- **Main text:** the German subtitles. They come with the video file, so they match its version.
- **No separate app:** all data stays in your files. A Claude Code plugin manages them.
- **Claude Code only:** all agent work runs in Claude Code with your login. No code calls the Claude API.
- **Tutor:** the agent is also a passive tutor. You can ask it questions at any time.

## Daily routine

Each Episode follows one fixed order: Lesson, then watch. Reviews are separate. This takes about 60 minutes.

| Step | Time | What you do |
| --- | --- | --- |
| Lesson | about 15 min | First the Word Knowledge Check. Then learn the Taught words and the Grammar topics. Do the exercises. |
| Watch | about 45 min | Watch the Episode in mpv. The player loads the tagged German subtitle file next to it. |
| Review | separate | Review earlier vocab and grammar, on their own schedules. |

In the first weeks, the Word Knowledge Check adds about 20 minutes. Almost all words are new then. After 5–10 Episodes, it gets much shorter. This is accepted.

You start the work with one of two requests to the agent:

1. **Lesson mode:** "Make the lesson for Dark S01E03."
2. **Review mode:** "Start a review session."

## System overview

You use three things: the video player, the exercise page, and the tutor chat. Everything else serves them.

```
 Video player              Exercise page              Tutor chat
 (mpv, tagged subtitles)   (Check, Lesson, Review)    (claude --agent tutor)
      ^                         |  answer, result          |
      |                         v                          v
      |                    Web server  --- grader --->  Agents
      |                    (Python, localhost)          (tutor + 3 subagents)
      | loads                   |  check, save             |
      | tagged .srt             |                          v
      |                         |                     MCP server
      |                         |                     (fixed tools for agents)
      |                         v                          |
      |                    Scripts  <----------------------+
      |                    (spaCy, word facts, frequency, LanguageTool, FSRS)
      |                         |  read, write
      |                         v
 +--------------------------------------------------------------------+
 | Your files: vocab DB, word facts, frequency table, curriculum,     |
 |             learner state, lessons, results, subtitles, video      |
 +--------------------------------------------------------------------+
```

The agents reach your files only through the MCP server. The exercise page reaches them only through the web server.

## Media folders

Each Episode has one fixed folder. The agent finds it from the name you give.

| Media | Folder | Episodes |
| --- | --- | --- |
| Series | `media/Dark/S01E03/` | One Episode per folder |
| Film | `media/Das-Boot/` | Parts `P1`, `P2`, `P3` |

- A film Episode is a time range in the same video file, for example 0:00–0:48. The video is not cut. You stop the player at the end of the range.
- The tagged subtitle file covers the full film. Each Lesson tags only the Lines in its own range.

## Episode processing pipeline

Scripts do the fixed steps. Agents do the steps that need judgment. Example sentences are written only for words you mark as Unknown, so no work is wasted on Known words.

**Part 1: processing (before the check)**

1. You download the Episode video with its German subtitles into the Episode folder. If the subtitles are inside the video file (for example an .mkv), a script extracts them as .srt (for example with ffmpeg). They belong to this video version, so the timing matches. The text can still differ a little from the speech. This is accepted.
2. A script reads the file. It splits it into Lines with start and end times.
3. spaCy splits each Line into words. It finds the Base form and the word type of each word. (spaCy is a free text-analysis tool.)
   - **Rule:** separable verbs join into one Base form. "Er gab nicht auf" gives **aufgeben**, not **geben**.
   - Names, places and other non-vocab words are filtered out.
4. A script checks each Base form against the vocab database. Only New words go on.
5. A script gets the facts for each New word from the kaikki.org data: meaning, gender, plural, verb forms. (kaikki.org gives the English Wiktionary as clean data. You download it one time. After that, it works offline.)
   - If a compound word is not in the data, the script splits it into its parts, for example "Mord" + "Kommission". The gender comes from the last part.
   - The agent writes the meaning of such a word. The card marks this meaning as "unchecked".

**Part 2: Word Knowledge Check**

6. The exercise page shows each New word: its Base form and word type only. It shows no episode Line, so there are no spoilers. You press one key per word:
   - **K** = Known word
   - **U** = Unknown word
   - **X** = Excluded word (a name, a filler sound, or parser junk that step 3 missed). It never comes back.

   A script runs the check, not an agent. There is no seeding of the database. The check covers all New words.

**Part 3: lesson build (after the check)**

7. A script picks up to 20 Unknown words, the most frequent first. The other Unknown words stay Unknown. A later Lesson teaches them when they appear again in an Episode. They get no reviews until then.
8. The sentence-writer agent writes 3 example sentences for each Taught word.
9. LanguageTool checks each sentence. (LanguageTool is a free grammar checker. The system uses its public server.) A failed sentence gets a retry, up to 3 times. After that, it goes on a list for you.
10. The topic-finder agent finds Grammar topics in the Lines.
11. A script compares these topics with the Curriculum and your learner state. It picks 2 topics: 1 new topic and 1 Weak point.
12. The topic-finder makes a stock of 5 exercises for each topic. LanguageTool checks them.
13. The agent builds the Lesson file and the tagged subtitle file.

The lesson build takes about 3–5 minutes. This wait is accepted.

## Frequency table

- The source is the hermitdave/FrequencyWords German list. It comes only from film and TV subtitles (OpenSubtitles 2018), so it matches your kind of German.
- The list counts word forms. A script runs it through spaCy one time and adds up the counts for each Base form. The result is a local table: Base form → count.
- A word that is not in the table goes last.

## Data and files

Your files are the single source of truth. Agents change them only through tools.

| File | What it holds | Who writes it |
| --- | --- | --- |
| Vocab database (SQLite) | Base form, meaning, gender, plural, verb forms, word state (Known, Unknown, Taught, Excluded), the episode Line, example sentences, review dates | Scripts only |
| Word facts | The kaikki.org data for German | You download it once |
| Frequency table | Base form → count | Script, once |
| Curriculum | The topic map: all standard German Grammar topics, in order | The agent drafts it once. You approve it. The agent can propose changes. |
| Learner state (SQLite) | A record of each Lesson. The Topic state of each topic. Weak points. | Scripts, after lessons and reviews |
| Learner summary | A short version of the learner state. The agent reads it at the start of each session. | Script |
| Exercise stock | Grammar exercises for each topic, for reviews | Agent, through a tool |
| Episode folder | The video file, the original .srt, the processed Lines, the tagged .srt | Scripts |
| Lesson file (`lesson-NNN.json`) | Lesson content, exercises, correct answers | Agent, through a tool |
| Results file (`lesson-NNN.results.json`) | Your answers and the corrections | Web server |

The agent reads the full lesson records only when it needs them. This keeps its context small.

## Lessons

The Lesson comes before the Episode. You do the full Lesson first, then you watch the full Episode. It teaches the words and grammar of the Episode, without spoilers.

**What a Lesson holds**

- **Vocab:** up to 20 Taught words, chosen from your Unknown words.
- **Grammar:** 2 Grammar topics, 1 new and 1 weak. The Lesson starts with an example. Then it teaches the full topic, with more cases.
- **Exercises:** done on the exercise page (see below).

**Sections**

- The Lesson follows the Episode in story order. It has 3 Sections of about 15 minutes each (0–15, 15–30, 30–45).
- Each word goes in the Section where you first hear it.
- The Section details stay light for now. The Lesson will get fine-tuning later.

**Spoiler rules**

- Each word is taught with a neutral example sentence, not with the episode Line.
- If an episode Line is used for grammar: change the names and cut the Line to the part with the topic.
- Teach plot words, such as "Mord" (murder), with a neutral example sentence.

**Tagged subtitles**

- The agent adds a short Tag to the end of some Lines in the German .srt. You see it on screen at the right moment.
  - Word Tag: the Base form of a Taught word, for example `Er gab nicht auf. [aufgeben]`. Only the first 2 times the word appears.
  - Grammar Tag: the Grammar topic, for example `Ich gebe es dem Mann. [Dativ]`. Only on the Lines the Lesson used.
- The Tag shows the Base form, not the meaning. So you must still remember the meaning.
- The script saves the file next to the video, with the same base name (for example `Episode.de.tagged.srt`). mpv loads it with the setting `sub-auto=fuzzy`. If not, you pick the tagged track in the subtitle menu.

## Review

Vocab and grammar are two separate categories. Each has its own review rules. Only Taught words get vocab reviews.

**Vocab review**

- FSRS sets the review dates. (FSRS is a spaced-repetition method: you see an item again just before you forget it.) A script calculates the dates with the `py-fsrs` library.
- A card always shows the word in context, not alone:
  - **First review:** the episode Line, with the word in bold. You have watched the Episode, so there is no spoiler.
  - **Later reviews:** a different example sentence each time, from the sentences the sentence-writer made.
- The card shows the Base form ("geben") and the Seen form ("gab").
- You say the meaning in your head. Then you grade yourself: Again, Hard, Good, or Easy.
- For nouns, you also type the article (der, die, das). A script checks it.
- If a Known word turns out to be unknown, you tell the tutor. It changes the word to Unknown.

**Grammar review**

- Each review uses a new exercise from the exercise stock. You learn the rule, not one sentence. When the stock is low, the agent makes more at the next lesson build. So a review never waits for the agent.
- The results update the Topic state:

| Topic state | When |
| --- | --- |
| Not seen | Start |
| Seen | A Lesson taught it |
| Learned | You passed its Lesson exercises |
| Solid | You passed 3 reviews in a row |

- A failed review sets the topic back to Learned. It becomes a Weak point.
- Grammar exercises run on the exercise page too.

**Daily limit**

- Max 50 vocab cards and 5 grammar exercises per day. The rest move to the next day.

## Curriculum

- The agent drafts the Curriculum one time, from a standard list of B1–C1 Grammar topics. You check it and approve it.
- You are B2, so A1–B1 topics start as Solid.

**Footnote for later:** to move on from a topic, you must really master it. That needs real exercises or tests. But the Lesson must stay light, because its job is to help you watch the Episode. So better grammar exercises are parked for later. For now, the simple rules above apply.

## Exercise page

All work on the page runs in one local page with 3 tabs: **Check**, **Lesson**, **Review**. It opens the current Lesson. Old Lessons stay in a list. The agent does not edit the page.

**How a check works**

1. The page shows `lesson-NNN.json` as exercises with text fields.
2. You type your answer and press "Check".
3. The page sends the answer to the web server.
4. The server checks it with the cheapest checker that works (table below).
5. The result comes back: right or wrong, the correction, a short reason.
6. The server saves your answer and the result to `lesson-NNN.results.json`. The page shows the result.
7. You press "Finish" at the end. A script updates your learner state at once.

| Exercise type | Checker | Cost |
| --- | --- | --- |
| Fill a gap ("mit ___ Mann" → "dem") | Script compares with the correct answer | Free, instant |
| Pick one option | Script | Free, instant |
| Type the article (der, die, das) | Script | Free, instant |
| Write your own sentence | LanguageTool, then the grader agent if needed | Low |
| Translate, or explain why | Grader agent | Low |

**The grader**

- The server runs it headless, with no chat: `claude -p --agent grader`. This is Claude Code with your login, not the API. It runs as its own process, outside your chat session.
- It gets only one exercise, your answer, and the correct answer. It does not see your learner state. This keeps each call small.
- It returns structured output: JSON in a shape you define. So the page shows each result the same way.
- The tutor reads your learner summary. It can name repeated mistakes when you ask.

**The web server**

- A small Python program (FastAPI or Flask) on your computer, at an address like `localhost:8000`.
- It exists because a web page alone cannot run Claude or write to your files.
- A command such as `/lesson` starts it and opens the page. It runs only while you study.
- The web server is the door for you. The MCP server is the door for the agents. Both use the same scripts.

## Plugin structure

One Claude Code plugin holds the whole system: agents, skills, the MCP server, hooks, scripts, and the web server. You start it with `claude --agent tutor`.

**Agents**

| Agent | How it runs | Job |
| --- | --- | --- |
| `tutor` | Main session, with `--agent` | Your chat. Runs lesson mode and review mode. Answers your questions. |
| `sentence-writer` | Subagent | Writes example sentences for Taught words |
| `topic-finder` | Subagent | Finds Grammar topics in the Lines. Makes the exercise stock. |
| `grader` | Headless, called by the web server | Checks one open answer. Returns fixed JSON. |

- All agents use `model: inherit` for now (the same model as your session).
- With `--agent`, the tutor's own instructions replace the default Claude Code instructions. It has only your tools.

**Skills**

- `lesson`: the steps for lesson mode, from processing to the Lesson file.
- `review`: the steps for review mode.

**MCP server (the agents' tools)**

The agents can act only through these tools. Example tools:

- `parse_subtitles`, `split_words`
- `vocab_lookup`, `vocab_add`, `vocab_update`
- `word_facts`, `grammar_check`
- `pick_lesson_words`, `schedule_reviews`, `curriculum_gaps`
- `write_lesson`, `add_exercises`, `tag_subtitles`, `read_results`

**Hooks**

- A hook blocks any direct write to the data files that does not go through a tool.

**One limit:** plugin subagents ignore the `hooks`, `mcpServers`, and `permissionMode` fields. So the MCP server and the hooks go at the plugin level, not in the agent files.

## Design rules

1. **The agent decides, the scripts do.** Fixed steps are scripts. Steps that need judgment are agent tasks.
2. **Claude Code only.** All agent work runs in Claude Code. No code calls the API.
3. **Tools only.** The agents change data only through MCP tools.
4. **Files are the truth.** All state lives in your files.
5. **Facts from data.** Gender, plural, and verb forms come from the word facts data, not from the agent's memory. A meaning the agent writes is marked "unchecked".
6. **Check every agent sentence.** LanguageTool checks it before it enters the database.
7. **Cheapest checker first.** A script checks fixed answers. The grader checks only open answers.
8. **Small context.** The agent reads the learner summary, not the full history. The grader sees one exercise only.
9. **No spoilers before the Episode.**
10. **Each Lesson belongs to its Episode.** A Lesson teaches only words and topics from its own Episode.

## Project setup

- Same repo (`vocab-harvester`). Clean start on a new branch. The old `src/` is deleted.
- The old database has only 16 words. It is not migrated.

## Parked items

- A model for each agent.
- Real exercises to master grammar (see the footnote under Curriculum).
- The details of the spaCy step.
- Do the processing and the check the evening before, so the Lesson is ready in the morning.
- Run LanguageTool on your computer (needs Java).
- Color the target word. The ASS subtitle format allows this.
- Capture a Line while you watch: one key press saves the current subtitle Line to the database (for example with an mpv script).
- Interactive practice beyond the exercises.
- Mods: a pane in the terminal, or extra tool-call guards.

**Dropped**

- The after-check. The Tags stay.
- Easy/hard sorting of new words. FSRS learns which words are hard from your reviews.
- Seeding the database from a frequency list. The Word Knowledge Check covers all New words.
- The close English translation line. The normal English subtitle and the vocab database are enough.
- Audio features (transcription, audio clips). You want reading support only. They stay possible later, because the video files are local.
