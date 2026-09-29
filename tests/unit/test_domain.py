from __future__ import annotations

from clipaso.domain.clips import clip_bounds, pick_non_overlapping, sentence_windows, signal_score
from clipaso.domain.models import ClipCandidate, Signal, SignalSet
from clipaso.domain.segmentation import build_sentences
from tests.conftest import make_words


def test_sentences_split_on_punctuation_and_pauses():
    words = make_words("Hola a todos. ¿Qué tal estáis hoy? Vamos allá con el tema.")
    sentences = build_sentences(words, min_duration=0.5)
    assert [s.text for s in sentences] == ["Hola a todos.", "¿Qué tal estáis hoy?", "Vamos allá con el tema."]
    assert all(s.words for s in sentences)


def test_sentences_split_on_long_pause_without_punctuation():
    words = make_words("uno dos tres") + make_words("cuatro cinco", start=5.0)
    assert len(build_sentences(words)) == 2


def test_sentences_respect_max_duration():
    words = make_words(" ".join(["palabra"] * 100))  # 40 s sin puntuación
    assert all(s.duration <= 14.0 for s in build_sentences(words, max_duration=14.0))


def test_sentence_windows_within_bounds(transcript):
    s = transcript.sentences
    for i, j in sentence_windows(s, min_duration=15, max_duration=30):
        assert 15 <= s[j].end - s[i].start <= 30


def test_clip_bounds_do_not_overlap_neighbours(transcript):
    s = transcript.sentences
    start, end = clip_bounds(s, 2, 5, transcript.duration)
    assert s[1].end <= start <= s[2].start
    assert s[5].end <= end <= s[6].start


def test_signal_score_renormalizes_missing_signals():
    sig = SignalSet(signals={"a": Signal(name="a", step=1.0, values=[1.0] * 10)})
    score, parts = signal_score(sig, {"a": 0.2, "missing": 0.8}, 0, 5)
    assert score == 1.0 and parts == {"a": 1.0}


def test_pick_non_overlapping_prefers_best():
    def c(s, e, sc):
        return ClipCandidate(start=s, end=e, first_sentence=0, last_sentence=0, score=sc)

    chosen = pick_non_overlapping([c(0, 30, 0.5), c(10, 40, 0.9), c(50, 80, 0.4)], limit=5)
    assert [(x.start, x.score) for x in chosen] == [(10, 0.9), (50, 0.4)]
