"""Recorte inteligente que sigue la cara principal.

1. Muestrea el clip a ~5 fps y detecta caras (YuNet, OpenCV).
2. Construye la trayectoria horizontal de la cara más grande, filtrando ruido.
3. Simula una cámara con zona muerta: no se mueve por pequeños gestos, sigue
   con suavidad los desplazamientos y salta de golpe en los cambios de plano.
4. Traduce la trayectoria a comandos `sendcmd` que mueven el `crop` de ffmpeg.

Si no hay una cara fiable (pantallas, planos generales, varias personas
alejadas) y el modo es `auto`, se usa fondo desenfocado.

El detector es intercambiable (`FaceDetector`); por defecto YuNet (OpenCV).
Mejora natural: detección de hablante activo (quién mueve los labios).
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from clipaso.adapters.reframing.simple import blur_pad_plan, center_crop_plan, even
from clipaso.domain.models import ClipCandidate, OutputProfile, SourceVideo
from clipaso.domain.ports import ReframePlan
from clipaso.infra.logging import get_logger
from clipaso.infra.registry import register

log = get_logger(__name__)

CROP_NAME = "crop@rf"


class FaceDetector(Protocol):
    def largest_face_center(self, frame_bgr: np.ndarray) -> tuple[float, float] | None:
        """Centro (x, y) normalizado 0..1 de la cara más grande, o None."""
        ...


YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)


class YuNetFaceDetector:
    """Detector neuronal ligero incluido en OpenCV (el modelo, ~230 KB, se descarga una vez)."""

    def __init__(self, model_dir: Path, analysis_width: int = 640, min_score: float = 0.7) -> None:
        import cv2

        self.cv2 = cv2
        self.width = analysis_width
        model = model_dir / "face_detection_yunet_2023mar.onnx"
        if not model.exists():
            model_dir.mkdir(parents=True, exist_ok=True)
            log.info("reframe.download_model", url=YUNET_URL)
            tmp = model.with_suffix(".tmp")
            urllib.request.urlretrieve(YUNET_URL, tmp)
            tmp.replace(model)
        self.net = cv2.FaceDetectorYN.create(str(model), "", (320, 320), score_threshold=min_score)
        self._size: tuple[int, int] | None = None

    def largest_face_center(self, frame_bgr: np.ndarray) -> tuple[float, float] | None:
        h, w = frame_bgr.shape[:2]
        size = (self.width, int(h * self.width / w))
        if size != self._size:
            self.net.setInputSize(size)
            self._size = size
        _, faces = self.net.detect(self.cv2.resize(frame_bgr, size))
        if faces is None or len(faces) == 0:
            return None
        # Filas: x, y, w, h, 5 landmarks, score. Se queda con la cara más grande.
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4]
        return float((x + fw / 2) / size[0]), float((y + fh / 2) / size[1])


@dataclass
class Track:
    times: np.ndarray  # segundos relativos al inicio del clip
    centers: np.ndarray  # x normalizada 0..1, NaN si no hay cara
    coverage: float


def sample_track(source: SourceVideo, clip: ClipCandidate, detector: FaceDetector, sample_fps: float) -> Track:
    import cv2

    cap = cv2.VideoCapture(str(source.path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, clip.start * 1000)
        fps = source.fps or 30.0
        every = max(1, int(round(fps / sample_fps)))
        total = int(clip.duration * fps)
        times, centers = [], []
        for i in range(total):
            if i % every:
                if not cap.grab():
                    break
                continue
            ok, frame = cap.read()
            if not ok:
                break
            found = detector.largest_face_center(frame)
            times.append(i / fps)
            centers.append(found[0] if found else np.nan)
    finally:
        cap.release()
    arr = np.array(centers, dtype=np.float64)
    coverage = float(np.mean(~np.isnan(arr))) if arr.size else 0.0
    return Track(times=np.array(times), centers=arr, coverage=coverage)


def camera_path(
    centers: np.ndarray, *, dead_zone: float, cut_jump: float, follow: float, median_window: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (posición de cámara 0..1, marca de corte) por muestra."""
    x = centers.copy()
    # Rellenar huecos: hacia delante y, al principio, hacia atrás.
    valid = np.flatnonzero(~np.isnan(x))
    if valid.size == 0:
        return np.full_like(x, 0.5), np.zeros(x.size, dtype=bool)
    x[: valid[0]] = x[valid[0]]
    for i in range(1, x.size):
        if np.isnan(x[i]):
            x[i] = x[i - 1]
    # Mediana deslizante: elimina detecciones espurias aisladas.
    half = median_window // 2
    padded = np.pad(x, half, mode="edge")
    x = np.array([np.median(padded[i : i + median_window]) for i in range(x.size)])

    cam = np.empty_like(x)
    cuts = np.zeros(x.size, dtype=bool)
    cam[0] = x[0]
    for i in range(1, x.size):
        delta = x[i] - cam[i - 1]
        if abs(x[i] - x[i - 1]) > cut_jump:
            cam[i] = x[i]  # cambio de plano: salto seco
            cuts[i] = True
        elif abs(delta) > dead_zone:
            cam[i] = cam[i - 1] + (delta - np.sign(delta) * dead_zone) * follow
        else:
            cam[i] = cam[i - 1]
    return cam, cuts


def sendcmd_script(
    times: np.ndarray,
    cam: np.ndarray,
    cuts: np.ndarray,
    *,
    src_w: int,
    crop_w: int,
    duration: float,
    rate: float = 15.0,
) -> tuple[int, str]:
    """Interpola la cámara a `rate` Hz (sin interpolar a través de cortes)."""

    def to_px(v: float) -> int:
        return int(np.clip(round(v * src_w - crop_w / 2), 0, src_w - crop_w)) // 2 * 2

    lines: list[str] = []
    last_px: int | None = None
    first_px = to_px(cam[0])
    for t in np.arange(0.0, duration, 1.0 / rate):
        j = int(np.searchsorted(times, t, side="right"))  # primera muestra posterior a t
        if j <= 0:
            v = cam[0]
        elif j >= times.size or cuts[j]:
            v = cam[j - 1]
        else:
            t0, t1 = times[j - 1], times[j]
            v = cam[j - 1] + (cam[j] - cam[j - 1]) * (t - t0) / max(t1 - t0, 1e-6)
        px = to_px(v)
        if last_px is None or abs(px - last_px) >= 2:
            lines.append(f"{t:.3f} {CROP_NAME} x {px};")
            last_px = px
    return first_px, "\n".join(lines) + "\n"


@register("reframers", "face")
@register("reframers", "auto")
class FaceTrackReframer:
    name = "face"

    def __init__(
        self,
        fallback_to_blur: bool = True,
        min_coverage: float = 0.5,
        sample_fps: float = 5.0,
        detector: FaceDetector | None = None,
        model_dir: Path | None = None,
        **_: Any,
    ) -> None:
        self.fallback_to_blur = fallback_to_blur
        self.min_coverage = min_coverage
        self.sample_fps = sample_fps
        self.model_dir = model_dir or Path("data/models")
        self._detector = detector

    @property
    def detector(self) -> FaceDetector:
        if self._detector is None:
            self._detector = YuNetFaceDetector(self.model_dir)
        return self._detector

    def plan(self, source: SourceVideo, clip: ClipCandidate, profile: OutputProfile) -> ReframePlan:
        W, H, fps = profile.width, profile.height, profile.fps
        src_aspect = source.width / source.height
        if src_aspect <= profile.aspect * 1.05:
            # El original ya es tan estrecho como la salida: no hay nada que recortar.
            return blur_pad_plan(profile, ["origen ya vertical/cuadrado"])

        crop_h = even(source.height)
        crop_w = even(crop_h * profile.aspect)
        track = sample_track(source, clip, self.detector, self.sample_fps)
        log.debug("reframe.track", samples=track.times.size, coverage=round(track.coverage, 2))

        if track.coverage < self.min_coverage:
            note = f"cara detectada solo en {track.coverage:.0%} del clip"
            if self.fallback_to_blur:
                return blur_pad_plan(profile, [note])
            if track.coverage < 0.1:
                return center_crop_plan(source, profile)

        crop_frac = crop_w / source.width
        cam, cuts = camera_path(
            track.centers,
            dead_zone=crop_frac * 0.12,
            cut_jump=0.18,
            follow=0.35,
        )
        x0, script = sendcmd_script(
            track.times, cam, cuts, src_w=source.width, crop_w=crop_w, duration=clip.duration
        )
        fc = (
            f"[0:v]sendcmd=f=reframe.cmd,{CROP_NAME}=w={crop_w}:h={crop_h}:x={x0}:y=0,"
            f"scale={W}:{H}:flags=lanczos,setsar=1,fps={fps}[vout]"
        )
        return ReframePlan(
            mode="face",
            filter_complex=fc,
            sendcmd=script,
            notes=[f"cobertura de cara {track.coverage:.0%}", f"cortes de plano {int(cuts.sum())}"],
        )
