"""Hace visibles en Windows las DLL de CUDA instaladas vía pip (extra `gpu`).

CTranslate2 (faster-whisper) necesita cuBLAS 12 y cuDNN 9. Los paquetes
`nvidia-*-cu12` las instalan dentro de site-packages, pero Windows no las
busca ahí: hay que añadir esas carpetas al PATH antes de cargar el modelo.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache
def register_nvidia_dlls() -> list[str]:
    if sys.platform != "win32":
        return []
    added: list[str] = []
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            added.append(str(bin_dir))
    return added


def cuda_device_count() -> int:
    register_nvidia_dlls()
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0
