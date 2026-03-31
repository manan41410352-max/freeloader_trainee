from __future__ import annotations

from pathlib import Path
from threading import Lock

import soundfile as sf
import torch
import torchaudio
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from app.config import AppConfig


_PIPELINE_LOCK = Lock()
_TRANSCRIBE_LOCK = Lock()
_TRANSCRIBER = None


def _load_transcriber(config: AppConfig, logger):
    global _TRANSCRIBER

    if _TRANSCRIBER is not None:
        return _TRANSCRIBER

    with _PIPELINE_LOCK:
        if _TRANSCRIBER is not None:
            return _TRANSCRIBER

        model_path = config.whisper_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"Whisper model was not found at {model_path}. "
                "Set WHISPER_MODEL_PATH if you moved it."
            )

        use_cuda = torch.cuda.is_available()
        device = 0 if use_cuda else -1
        torch_dtype = torch.float16 if use_cuda else torch.float32

        logger.info(
            "Loading local voice model from %s using %s",
            model_path,
            "cuda" if use_cuda else "cpu",
        )

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            str(model_path),
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            local_files_only=True,
        )
        if use_cuda:
            model.to("cuda:0")

        processor = AutoProcessor.from_pretrained(
            str(model_path),
            local_files_only=True,
        )

        _TRANSCRIBER = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            dtype=torch_dtype,
            device=device,
        )
        return _TRANSCRIBER


def warm_transcriber(config: AppConfig, logger) -> dict:
    _load_transcriber(config, logger)
    return {
        "ready": True,
        "model_path": str(config.whisper_model_path),
    }


def transcribe_audio_file(audio_path: Path, config: AppConfig, logger) -> str:
    transcriber = _load_transcriber(config, logger)

    audio, sample_rate = sf.read(str(audio_path), dtype="float32")
    if audio.size == 0:
        raise ValueError("Recorded audio was empty.")

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    waveform = torch.from_numpy(audio).float()
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)

    target_sample_rate = 16000
    if sample_rate != target_sample_rate:
        waveform = torchaudio.functional.resample(waveform, sample_rate, target_sample_rate)
        sample_rate = target_sample_rate

    audio_array = waveform.squeeze(0).contiguous().cpu().numpy()

    with _TRANSCRIBE_LOCK, torch.inference_mode():
        result = transcriber(
            {"array": audio_array, "sampling_rate": sample_rate},
            generate_kwargs={
                "task": "transcribe",
                "language": "en",
            },
        )

    transcript = str(result.get("text") or "").strip()
    if not transcript:
        raise RuntimeError("Local speech model returned an empty transcript.")

    logger.info("Voice transcription completed with %s characters", len(transcript))
    return transcript
