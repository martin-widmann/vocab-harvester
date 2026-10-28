# German Media Learning

A daily system that teaches German from German films and series. Each Episode gets a Lesson before the learner watches it.

## Media

**Episode**:
One watch unit of about 45 minutes. A series episode is one Episode; a film is two or three Episodes, each a time range of the same video.
_Avoid_: Part, video, film

**Line**:
One subtitle entry of an Episode, with its start and end time.
_Avoid_: Subtitle, cue, sentence

**Tag**:
A short note in square brackets at the end of a Line, seen while watching. It names a Taught word by its Base form, or a Grammar topic.
_Avoid_: Label, marker, annotation

## Vocabulary

**Base form**:
The dictionary form of a word, for example "geben".
_Avoid_: Lemma, root, word

**Seen form**:
The form of a word as it appears in a Line, for example "gab".
_Avoid_: Token, inflection

**New word**:
A Base form from an Episode that is not yet in the learner's vocabulary.
_Avoid_: Unknown word (an Unknown word is a New word the learner has marked)

**Known word**:
A Base form the learner has marked as already known.

**Unknown word**:
A Base form the learner has marked as not known. It waits until it appears in an Episode whose Lesson teaches it.

**Taught word**:
An Unknown word that a Lesson has taught. Only Taught words get reviews.
_Avoid_: Learned word, studied word

**Excluded word**:
A Base form that is not vocabulary: a name, a place, a filler sound, or parser junk. It is never shown again.
_Avoid_: Ignored word, stopword, "not a word"

## Grammar

**Grammar topic**:
One rule of standard German grammar, for example the dative case.
_Avoid_: Rule, grammar point, concept

**Curriculum**:
The ordered map of all Grammar topics the learner wants to learn.
_Avoid_: Syllabus, topic list, roadmap

**Topic state**:
How far the learner is with a Grammar topic: Not seen, Seen (a Lesson taught it), Learned (its Lesson exercises passed), or Solid (three reviews passed in a row).
_Avoid_: Level, progress, mastery

**Weak point**:
A Taught word or Grammar topic the learner recently failed. It comes back sooner in reviews.
_Avoid_: Mistake, gap

## Lessons

**Lesson**:
The study session for one Episode, done in full before watching it. It teaches up to 20 of the Episode's Unknown words, the most frequent first, and its grammar topics.
_Avoid_: Class, unit

**Section**:
A time slice of about 15 minutes of an Episode. The Lesson follows the Sections in story order.
_Avoid_: Chapter, scene, part

**Word Knowledge Check**:
The first step of a Lesson, where the learner marks each New word of the Episode as a Known word, an Unknown word or an Excluded word.
_Avoid_: Sort, first review, placement test
