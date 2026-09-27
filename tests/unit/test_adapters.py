from __future__ import annotations

import numpy as np
import pytest

from smartcuts.adapters.exporters.subtitles import ass_color, ass_time, build_ass
from smartcuts.adapters.reframing.face_track import camera_path, sendcmd_script
from smartcuts.application.workspace import Workspace
from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.models import SubtitleStyle, Transcript
from smartcuts.infra import registry
from tests.conftest import make_words


def test_registry_unknown_name():
    import smartcuts.adapters  # noqa: F401

    with pytest.raises(ConfigurationError, match="Disponibles"):
        registry.create("selectors", "no-existe")


def test_workspace_cache_invalidates_on_param_change(tmp_path):
    ws = Workspace(tmp_path)
    t = Transcript(language="es", duration=1, sentences=[])
    ws.save("transcript", t, {"model": "a"})
    assert ws.load("transcript", Transcript, {"model": "a"}) == t
    assert ws.load("transcript", Transcript, {"model": "b"}) is None


def test_ass_helpers():
    assert ass_color("00E5FF") == "&H00FFE500"
    assert ass_time(3723.456) == "1:02:03.46"


def test_build_ass_highlights_each_word():
    words = make_words("hola qué tal. esto va bien")
    ass = build_ass(words, SubtitleStyle(max_words=3), 1080, 1920)
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue")]
    assert len(dialogues) == len(words)
    assert "{\\c&H00FFE500}HOLA{\\c&H00FFFFFF} QUÉ TAL" in dialogues[0]
    assert "PlayResY: 1920" in ass


def test_camera_holds_still_inside_dead_zone_and_jumps_on_cut():
    centers = np.array([0.50, 0.52, 0.49, 0.51, 0.50, 0.85, 0.86, 0.85, 0.84, 0.85])
    cam, cuts = camera_path(centers, dead_zone=0.05, cut_jump=0.18, follow=0.35, median_window=1)
    assert np.allclose(cam[:5], 0.50)
    assert cuts[5] and cam[5] == pytest.approx(0.85)


def test_camera_fills_missing_detections():
    centers = np.array([np.nan, np.nan, 0.3, np.nan, 0.3])
    cam, _ = camera_path(centers, dead_zone=0.05, cut_jump=0.5, follow=0.5, median_window=1)
    assert np.allclose(cam, 0.3)


def test_sendcmd_script_clamps_to_frame():
    times = np.array([0.0, 1.0])
    cam = np.array([0.0, 1.0])
    x0, script = sendcmd_script(times, cam, np.array([False, False]), src_w=1920, crop_w=606, duration=1.0)
    xs = [int(line.split()[-1].rstrip(";")) for line in script.strip().splitlines()]
    assert x0 == 0 and min(xs) >= 0 and max(xs) <= 1920 - 606
    assert all(x % 2 == 0 for x in xs)
