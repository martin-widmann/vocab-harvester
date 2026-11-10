---
name: lesson
description: Make the Lesson of an Episode from one request, from the subtitles to the tagged subtitle file. Use when the learner types /lesson, or says "Make the lesson for Dark S01E03", or asks to open the page or to do the Word Knowledge Check.
argument-hint: <Series S01E03 | Film P2>
---

Make the Lesson for the Episode `$ARGUMENTS`. Do the steps in this order. Each step uses the result of the step before it.

## 1. Find the Episode

1. If no Episode is given above, ask the learner which Episode, for example "Dark S01E03" or "Der Untergang P2". Then continue.
2. Call `mcp__plugin_german-media-learning_learning__find_episode` with the name as the learner wrote it. Turn words into a code first: "Dark season 1 episode 3" is "Dark S01E03", "Der Untergang part 2" is "Der Untergang P2".
3. If it gives an error, tell the learner the error in one sentence, with the Episodes it names, and ask for the correct Episode. Stop.
4. Use the `episode` from the result (for example `Dark/S01E03`) in every later step.
5. If `lesson` is a number, the Episode has a Lesson already. Call `mcp__plugin_german-media-learning_learning__open_page` with the Episode, give the learner the URL, and say the Lesson is on the Lesson tab. Stop. Build it again only if the learner asks for that.

## 2. Process the Episode

1. Call `mcp__plugin_german-media-learning_learning__new_words` with the Episode.
2. Report the number of New words and show the first 10 as "Base form (word type)". Do not show meanings: the Word Knowledge Check shows no spoilers.

## 3. Word Knowledge Check

1. Call `mcp__plugin_german-media-learning_learning__open_page` with the Episode. Give the learner the URL.
2. If there are New words, tell the learner: "Mark each word on the Check tab: K Known, U Unknown, X Excluded. I wait until you are done." If there are no New words, say there is nothing to check, and go to step 4.
3. Call `mcp__plugin_german-media-learning_learning__wait_for_check` with the Episode.
4. If `done` is false, call `mcp__plugin_german-media-learning_learning__wait_for_check` again. Every 5th time, tell the learner in one line how many words are `left`. Repeat until `done` is true.
5. The learner can press Esc to stop the wait. Then stop. When the learner asks for the Lesson again, start at step 1: the marked words do not come back.

## 4. Pick the Lesson words

1. Call `mcp__plugin_german-media-learning_learning__pick_lesson_words` with the Episode. It gives up to 20 Unknown words, the most frequent first.
2. Tell the learner how many words the Lesson teaches.

## 5. Example sentences

Only the picked words get sentences. Never give the sentence-writer any other word.

1. If no word is picked, go to step 6.
2. Start the `german-media-learning:sentence-writer` subagent. Give it the Episode name and each picked word as "Base form (word type)", nothing else. Do not give it the Lines: the sentences must not spoil the plot.
3. If it reports an error, tell the learner the error in one sentence. Stop.

## 6. Grammar topics, Lesson and Tags

1. Start the `german-media-learning:topic-finder` subagent with the Episode name. It finds the Grammar topics in the Lines. The core picks the 2 topics that the Lesson teaches: 1 new topic and 1 Weak point. The topic-finder fills the exercise stock and writes the Lesson file. Then the core writes the tagged subtitle file (the Tags) next to the video.
2. If it says there is no Curriculum yet, tell the learner, and draft one (see "The Curriculum" in your instructions). After the learner approves it, start the topic-finder again.
3. If it reports another error, tell the learner the error in one sentence. Then do step 7.1 and 7.3 only, and stop.

## 7. The end

1. Call `mcp__plugin_german-media-learning_learning__failed_sentences` with the Episode.
2. Tell the learner, in a few lines:
   - the Lesson number, and how many words it teaches;
   - the 2 Grammar topics, or that the Episode has none;
   - the name of the tagged subtitle file, from the reply of the topic-finder;
   - that the Lesson is on the Lesson tab of the page (call `mcp__plugin_german-media-learning_learning__open_page` again if the page is not open).
3. If `failed_sentences` gives sentences, show each one with its Base form, number, sentence and problems. They are not stored.
   - Status `listed`: say "This sentence failed LanguageTool on all its tries. The Lesson has one sentence less for the word."
   - Status `retry`: say "The sentence-writer stopped before it wrote a new sentence." Then the Lesson is not written: ask the learner whether to make the Lesson again.
4. If the topic-finder named topics that are not in the Curriculum, ask the learner whether to propose a change.
