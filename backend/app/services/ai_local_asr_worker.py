"""Disposable local model process. No HTTP client, files or diagnostic audio."""
import io
import json
import sys
import wave


def main():
    import numpy as np  # type: ignore[import-not-found]
    import onnxruntime  # type: ignore[import-not-found]

    onnxruntime.disable_telemetry_events()

    # Standalone process: avoid importing the web application's package initializer
    # and its unrelated dependencies into the isolated ASR environment.
    from ai_local_asr import validate_pcm  # type: ignore[import-not-found]
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    audio = sys.stdin.buffer.read(480_045)
    validate_pcm(audio)
    with wave.open(io.BytesIO(audio), "rb") as wav:
        samples = np.frombuffer(wav.readframes(240000), dtype="<i2").astype(np.float32)/32768
    model = WhisperModel(sys.argv[1], device="cpu", compute_type="int8", cpu_threads=2,
                         num_workers=1, local_files_only=True)
    segments, _ = model.transcribe(samples, beam_size=1, vad_filter=True, condition_on_previous_text=False,
                                   without_timestamps=True, max_new_tokens=96)
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    if not 1 <= len(transcript) <= 160:
        raise ValueError("VOICE_TRANSCRIPT_INVALID")
    sys.stdout.write(json.dumps(transcript, ensure_ascii=True))


if __name__ == "__main__":
    main()
