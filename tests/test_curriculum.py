"""Curriculum and Topic state: the ordered map of Grammar topics and how far the learner is."""

import pytest

from core import Curriculum, Topic, TopicState, VocabStore, WordState, curriculum_gaps

DRAFT = [
    Topic("perfekt", "Perfekt", "A2"),
    Topic("dativ", "Dativ", "A2"),
    Topic("relativsatz", "Relativsatz", "B1"),
    Topic("passiv-modalverb", "Passiv mit Modalverb", "B2"),
    Topic("konjunktiv-1", "Konjunktiv I", "B2"),
    Topic("partizipialattribut", "Partizipialattribut", "C1"),
]


@pytest.fixture
def curriculum(tmp_path):
    return Curriculum(tmp_path / "vocab.sqlite")


def approved(curriculum, topics=DRAFT):
    proposal = curriculum.propose(topics)
    curriculum.approve(proposal.number)
    return curriculum


def states(curriculum):
    return {status.topic.id: status.state for status in curriculum.topics()}


def test_a_draft_is_not_stored_as_the_curriculum_before_the_learner_approves_it(curriculum):
    curriculum.propose(DRAFT)

    assert curriculum.topics() == []
    assert curriculum.proposal().topics == DRAFT


def test_an_approved_draft_becomes_the_curriculum_in_its_order(curriculum):
    approved(curriculum)

    assert [status.topic for status in curriculum.topics()] == DRAFT
    assert curriculum.proposal() is None


def test_a1_to_b1_topics_start_as_solid_and_the_others_as_not_seen(curriculum):
    approved(curriculum)

    assert states(curriculum) == {
        "perfekt": TopicState.SOLID,
        "dativ": TopicState.SOLID,
        "relativsatz": TopicState.SOLID,
        "passiv-modalverb": TopicState.NOT_SEEN,
        "konjunktiv-1": TopicState.NOT_SEEN,
        "partizipialattribut": TopicState.NOT_SEEN,
    }


def test_only_the_proposal_the_learner_saw_can_be_approved(curriculum):
    first = curriculum.propose(DRAFT)
    second = curriculum.propose(DRAFT[:2])

    with pytest.raises(ValueError, match="not the open proposal"):
        curriculum.approve(first.number)
    assert curriculum.topics() == []

    curriculum.approve(second.number)
    assert [status.topic for status in curriculum.topics()] == DRAFT[:2]


def test_with_no_open_proposal_there_is_nothing_to_approve(curriculum):
    approved(curriculum)

    with pytest.raises(ValueError, match="No open proposal"):
        curriculum.approve(1)


def status_of(curriculum, topic_id):
    (status,) = [s for s in curriculum.topics() if s.topic.id == topic_id]
    return status


def test_a_topic_a_lesson_teaches_becomes_seen(curriculum):
    approved(curriculum).taught("konjunktiv-1")

    assert status_of(curriculum, "konjunktiv-1").state == TopicState.SEEN


def test_a_seen_topic_whose_lesson_exercises_passed_becomes_learned(curriculum):
    approved(curriculum).taught("konjunktiv-1")

    curriculum.lesson_exercises_passed("konjunktiv-1")

    assert status_of(curriculum, "konjunktiv-1").state == TopicState.LEARNED


def learned(curriculum, topic_id="konjunktiv-1"):
    curriculum.taught(topic_id)
    curriculum.lesson_exercises_passed(topic_id)
    return curriculum


def test_a_learned_topic_becomes_solid_after_three_reviews_passed_in_a_row(curriculum):
    learned(approved(curriculum))

    curriculum.review("konjunktiv-1", passed=True)
    curriculum.review("konjunktiv-1", passed=True)
    assert status_of(curriculum, "konjunktiv-1").state == TopicState.LEARNED

    curriculum.review("konjunktiv-1", passed=True)
    assert status_of(curriculum, "konjunktiv-1").state == TopicState.SOLID


def test_a_failed_review_breaks_the_row_of_passed_reviews(curriculum):
    learned(approved(curriculum))

    for passed in (True, True, False, True, True):
        curriculum.review("konjunktiv-1", passed=passed)
    assert status_of(curriculum, "konjunktiv-1").state == TopicState.LEARNED

    curriculum.review("konjunktiv-1", passed=True)
    assert status_of(curriculum, "konjunktiv-1").state == TopicState.SOLID


def test_a_failed_review_sets_a_solid_topic_back_to_learned_as_a_weak_point(curriculum):
    approved(curriculum)

    curriculum.review("dativ", passed=False)

    status = status_of(curriculum, "dativ")
    assert status.state == TopicState.LEARNED
    assert status.weak


def test_a_weak_point_stops_being_weak_when_the_topic_is_solid_again(curriculum):
    approved(curriculum).review("dativ", passed=False)

    for _ in range(3):
        curriculum.review("dativ", passed=True)

    status = status_of(curriculum, "dativ")
    assert status.state == TopicState.SOLID
    assert not status.weak


def test_teaching_a_topic_again_does_not_set_it_back(curriculum):
    learned(approved(curriculum))

    curriculum.taught("konjunktiv-1")
    curriculum.taught("dativ")

    assert status_of(curriculum, "konjunktiv-1").state == TopicState.LEARNED
    assert status_of(curriculum, "dativ").state == TopicState.SOLID


def test_lesson_exercises_of_a_topic_no_lesson_taught_change_nothing(curriculum):
    approved(curriculum).lesson_exercises_passed("konjunktiv-1")

    assert status_of(curriculum, "konjunktiv-1").state == TopicState.NOT_SEEN


@pytest.mark.parametrize("taught", [False, True], ids=["not seen", "seen"])
def test_a_topic_is_not_reviewed_before_it_is_learned(curriculum, taught):
    approved(curriculum)
    if taught:
        curriculum.taught("konjunktiv-1")

    with pytest.raises(ValueError, match="not Learned"):
        curriculum.review("konjunktiv-1", passed=True)


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.taught("futur-2"),
        lambda c: c.lesson_exercises_passed("futur-2"),
        lambda c: c.review("futur-2", passed=True),
    ],
    ids=["taught", "exercises", "review"],
)
def test_a_topic_that_is_not_in_the_curriculum_has_no_topic_state(curriculum, change):
    approved(curriculum)

    with pytest.raises(ValueError, match="not in the Curriculum"):
        change(curriculum)


CHANGED = [
    Topic("konjunktiv-1", "Konjunktiv I (indirekte Rede)", "B2"),
    Topic("dativ", "Dativ", "A2"),
    Topic("futur-2", "Futur II", "B2"),
    Topic("plusquamperfekt", "Plusquamperfekt", "B1"),
    Topic("partizipialattribut", "Partizipialattribut", "C1"),
]


def test_a_proposed_change_applies_only_after_the_learner_approves_it(curriculum):
    approved(curriculum)

    curriculum.propose(CHANGED)

    assert [status.topic for status in curriculum.topics()] == DRAFT


def test_a_proposed_change_names_the_topics_it_adds_and_removes(curriculum):
    approved(curriculum)

    proposal = curriculum.propose(CHANGED)

    assert proposal.added == ["futur-2", "plusquamperfekt"]
    assert proposal.removed == ["perfekt", "relativsatz", "passiv-modalverb"]


def test_an_approved_change_keeps_the_topic_state_of_the_topics_it_keeps(curriculum):
    learned(approved(curriculum))
    curriculum.review("dativ", passed=False)

    curriculum.approve(curriculum.propose(CHANGED).number)

    assert [status.topic for status in curriculum.topics()] == CHANGED
    assert states(curriculum) == {
        "konjunktiv-1": TopicState.LEARNED,
        "dativ": TopicState.LEARNED,
        "futur-2": TopicState.NOT_SEEN,
        "plusquamperfekt": TopicState.SOLID,
        "partizipialattribut": TopicState.NOT_SEEN,
    }
    assert status_of(curriculum, "dativ").weak


def test_a_removed_topic_has_no_topic_state_any_more(curriculum):
    approved(curriculum)
    curriculum.approve(curriculum.propose(CHANGED).number)

    with pytest.raises(ValueError, match="not in the Curriculum"):
        curriculum.taught("passiv-modalverb")


@pytest.mark.parametrize(
    "topics, problem",
    [
        ([], "no Grammar topics"),
        ([Topic("dativ", "Dativ", "A2"), Topic("dativ", "Dativ 2", "B1")], "twice"),
        ([Topic("dativ", "Dativ", "B3")], "level"),
        ([Topic("dativ", " ", "A2")], "name"),
        ([Topic("Dativ Fall", "Dativ", "A2")], "id"),
    ],
    ids=["empty", "same id twice", "bad level", "no name", "bad id"],
)
def test_a_malformed_proposal_is_rejected_and_not_kept(curriculum, topics, problem):
    with pytest.raises(ValueError, match=problem):
        curriculum.propose(topics)

    assert curriculum.proposal() is None


ALL_IDS = [topic.id for topic in DRAFT]


def test_the_next_new_topic_is_the_first_not_seen_topic_in_curriculum_order(curriculum):
    approved(curriculum)

    gaps = curriculum_gaps(curriculum, ALL_IDS)

    assert gaps.new == Topic("passiv-modalverb", "Passiv mit Modalverb", "B2")


def test_the_next_new_topic_comes_only_from_the_topics_found_in_the_episode(curriculum):
    approved(curriculum)

    gaps = curriculum_gaps(curriculum, ["partizipialattribut", "dativ"])

    assert gaps.new.id == "partizipialattribut"


def test_a_topic_a_lesson_taught_is_not_new_any_more(curriculum):
    approved(curriculum).taught("passiv-modalverb")

    assert curriculum_gaps(curriculum, ALL_IDS).new.id == "konjunktiv-1"


def test_with_no_weak_point_in_the_episode_there_is_no_weak_topic(curriculum):
    approved(curriculum).review("dativ", passed=False)

    gaps = curriculum_gaps(curriculum, ["perfekt", "konjunktiv-1"])

    assert gaps.weak is None
    assert gaps.new.id == "konjunktiv-1"


def test_the_weak_topic_is_the_weak_point_that_has_been_weak_the_longest(curriculum):
    approved(curriculum)
    curriculum.review("relativsatz", passed=False)
    curriculum.review("dativ", passed=False)
    curriculum.review("relativsatz", passed=False)

    gaps = curriculum_gaps(curriculum, ["dativ", "relativsatz"])

    assert gaps.weak == Topic("relativsatz", "Relativsatz", "B1")


def test_a_weak_point_that_is_solid_again_is_not_the_weak_topic(curriculum):
    approved(curriculum).review("dativ", passed=False)
    for _ in range(3):
        curriculum.review("dativ", passed=True)

    assert curriculum_gaps(curriculum, ALL_IDS).weak is None


def test_with_nothing_left_to_learn_there_is_no_new_topic(curriculum):
    approved(curriculum)

    gaps = curriculum_gaps(curriculum, ["perfekt", "dativ"])

    assert gaps.new is None
    assert gaps.weak is None


def test_found_topics_that_are_not_in_the_curriculum_are_named(curriculum):
    approved(curriculum)

    gaps = curriculum_gaps(curriculum, ["futur-2", "dativ", "futur-2", "n-deklination"])

    assert gaps.not_in_curriculum == ["futur-2", "n-deklination"]


def test_there_are_no_gaps_before_the_learner_approved_a_curriculum(curriculum):
    curriculum.propose(DRAFT)

    with pytest.raises(ValueError, match="No Curriculum"):
        curriculum_gaps(curriculum, ALL_IDS)


def test_the_curriculum_and_topic_states_stay_in_the_vocab_file(tmp_path):
    path = tmp_path / "vocab.sqlite"
    VocabStore(path).add("geben", "VERB", WordState.KNOWN)
    first = Curriculum(path)
    approved(first).review("dativ", passed=False)
    first.close()

    again = Curriculum(path)

    assert status_of(again, "dativ").weak
    assert [status.topic for status in again.topics()] == DRAFT
    assert VocabStore(path).state_of("geben") == WordState.KNOWN
