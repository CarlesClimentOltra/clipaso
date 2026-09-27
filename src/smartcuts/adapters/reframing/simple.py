"""Reencuadres que no necesitan analizar el vídeo."""

from __future__ import annotations

from typing import Any

from smartcuts.domain.models import ClipCandidate, OutputProfile, SourceVideo
from smartcuts.domain.ports import ReframePlan
from smartcuts.infra.registry import register


def even(value: float) -> int:
    return max(2, int(round(value / 2)) * 2)


def blur_pad_plan(profile: OutputProfile, notes: list[str] | None = None) -> ReframePlan:
    W, H, fps = profile.width, profile.height, profile.fps
    # El fondo se desenfoca a 1/4 de resolución y se reescala: mismo efecto, mucho más barato.
    bw, bh = even(W / 4), even(H / 4)
    fc = (
        f"[0:v]split=2[bgsrc][fgsrc];"
        f"[bgsrc]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
        f"boxblur=luma_radius=12:luma_power=2,eq=brightness=-0.06,scale={W}:{H}[bg];"
        f"[fgsrc]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps}[vout]"
    )
    return ReframePlan(mode="blur_pad", filter_complex=fc, notes=notes or [])


def center_crop_plan(source: SourceVideo, profile: OutputProfile) -> ReframePlan:
    W, H, fps = profile.width, profile.height, profile.fps
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"setsar=1,fps={fps}[vout]"
    )
    return ReframePlan(mode="center", filter_complex=fc)


@register("reframers", "blur_pad")
class BlurPadReframer:
    name = "blur_pad"

    def __init__(self, **_: Any) -> None:
        pass

    def plan(self, source: SourceVideo, clip: ClipCandidate, profile: OutputProfile) -> ReframePlan:
        return blur_pad_plan(profile)


@register("reframers", "center")
class CenterCropReframer:
    name = "center"

    def __init__(self, **_: Any) -> None:
        pass

    def plan(self, source: SourceVideo, clip: ClipCandidate, profile: OutputProfile) -> ReframePlan:
        return center_crop_plan(source, profile)
