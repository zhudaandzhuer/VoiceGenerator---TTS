#!/usr/bin/env python3
"""Local WeSpeaker embedding inference with a safe feature-gate fallback."""

from __future__ import annotations

import math
import subprocess
import threading
from pathlib import Path
from typing import Any

from paths import resolve_workspace_root


MODEL_RELATIVE = Path("outputs/models/wespeaker-cnceleb-resnet34/cnceleb_resnet34.onnx")
MODEL_SHA256 = "78817ca21a9707ad886d50745162231027a09c997fbf2ecf741c5d8ff4db1bf8"
_SESSION: Any = None
_SESSION_LOCK = threading.Lock()


def model_path() -> Path:
    return resolve_workspace_root() / MODEL_RELATIVE


def runtime_status() -> dict[str, Any]:
    path = model_path()
    try:
        import onnxruntime  # noqa: F401
        import torch  # noqa: F401
        import torchaudio  # noqa: F401
    except (ImportError, OSError) as exc:
        return {"available": False, "provider": "fallback", "error": f"{type(exc).__name__}: {exc}"}
    if not path.exists():
        return {"available": False, "provider": "fallback", "error": "WeSpeaker model is not installed"}
    return {
        "available": True,
        "provider": "wespeaker-cnceleb-resnet34-onnx",
        "model": str(path),
        "modelSha256": MODEL_SHA256,
        "device": "CPU / Apple Silicon",
    }


def _session() -> Any:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            return _SESSION
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 2
        _SESSION = ort.InferenceSession(str(model_path()), sess_options=options, providers=["CPUExecutionProvider"])
    return _SESSION


def _fbank(audio_path: Path) -> Any:
    import numpy as np
    import torch
    import torchaudio.compliance.kaldi as kaldi

    converted = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio_path), "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if converted.returncode != 0 or not converted.stdout:
        error = converted.stderr.decode("utf-8", errors="replace")[:500]
        raise ValueError(f"ffmpeg 無法解碼聲音錨點：{error}")
    samples = np.frombuffer(converted.stdout, dtype="<i2").astype(np.float32, copy=True) / 32768.0
    waveform = torch.from_numpy(samples).unsqueeze(0)
    sample_rate = 16000
    if waveform.shape[1] < int(sample_rate * 0.4):
        raise ValueError("聲紋 embedding 至少需要 0.4 秒有效音訊")
    waveform = waveform * (1 << 15)
    features = kaldi.fbank(
        waveform,
        num_mel_bins=80,
        frame_length=25,
        frame_shift=10,
        dither=0.0,
        sample_frequency=sample_rate,
        window_type="hamming",
        use_energy=False,
    )
    features = features - torch.mean(features, dim=0)
    return features.unsqueeze(0).numpy()


def extract_embedding(audio_path: Path) -> list[float]:
    status = runtime_status()
    if not status["available"]:
        raise RuntimeError(str(status.get("error", "speaker embedding runtime unavailable")))
    import numpy as np

    session = _session()
    output_name = session.get_outputs()[0].name
    input_name = session.get_inputs()[0].name
    embedding = session.run([output_name], {input_name: _fbank(audio_path)})[0]
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 1e-9:
        raise RuntimeError("WeSpeaker returned an invalid embedding")
    return (vector / norm).tolist()


def cosine_similarity(first: list[float], second: list[float]) -> float:
    if not first or len(first) != len(second):
        raise ValueError("speaker embeddings are incompatible")
    return max(-1.0, min(1.0, sum(left * right for left, right in zip(first, second))))


def decision_for(cosine: float) -> str:
    """Map a raw cosine score to the conservative production review policy."""
    return "pass" if cosine >= 0.55 else "review" if cosine >= 0.35 else "fail"


def compare(reference_path: Path, take_path: Path) -> dict[str, Any]:
    status = runtime_status()
    if not status["available"]:
        return {**status, "cosineSimilarity": None, "score": None, "decision": "unavailable"}
    try:
        reference = extract_embedding(reference_path)
        take = extract_embedding(take_path)
        cosine = round(cosine_similarity(reference, take), 6)
        # This score intentionally keeps the raw cosine visible. Thresholds are
        # conservative production gates, not a legal or biometric identity claim.
        score = round(max(0.0, min(100.0, cosine * 100.0)), 1)
        decision = decision_for(cosine)
        return {
            **status,
            "cosineSimilarity": cosine,
            "score": score,
            "decision": decision,
            "embeddingDimensions": len(reference),
            "policy": {"pass": ">= 0.55", "review": "0.35–0.55", "fail": "< 0.35"},
        }
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return {
            **status,
            "available": False,
            "cosineSimilarity": None,
            "score": None,
            "decision": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
