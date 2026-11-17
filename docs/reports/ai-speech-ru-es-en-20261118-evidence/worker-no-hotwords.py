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

    class HousingWhisperModel(WhisperModel):
        def encode(self, features):
            # faster-whisper encodes the first window once for language detection
            # and again for decoding. Reuse only byte-identical features within
            # this disposable worker; different windows always encode normally.
            cached = getattr(self, "_housing_encoded", None)
            if cached is not None and np.array_equal(features, cached[0]):
                return cached[1]
            encoded = super().encode(features)
            self._housing_encoded = (features.copy(), encoded)
            return encoded

        def detect_language(self, *args, **kwargs):
            # The product accepts Russian, Spanish and English speech. Short
            # Russian price phrases can otherwise be misclassified as Polish.
            # Reuse the detector's probabilities without encoding audio again.
            # Pinned faster-whisper1.2.1 decodes shape[-1]-1 content frames.
            # Use that exact same window for detection, so encode() can reuse it
            # without approximating or dropping any decoded audio features.
            features = kwargs.get("features")
            if features is not None:
                kwargs = {**kwargs, "features": features[..., :-1]}
            _, _, probabilities = super().detect_language(*args, **kwargs)
            language, probability = max(
                ((language, probability) for language, probability in probabilities
                 if language in {"ru", "es", "en"}), key=lambda item: item[1]
            )
            return language, probability, probabilities

    if len(sys.argv) > 3 or (len(sys.argv) == 3 and sys.argv[2] != "--prewarm"):
        raise ValueError("VOICE_WORKER_MODE_INVALID")

    def load_model():
        return HousingWhisperModel(sys.argv[1], device="cpu", compute_type="int8", cpu_threads=2,
                                   num_workers=1, local_files_only=True)

    model = load_model() if len(sys.argv) == 3 else None
    if model is not None:
        # Only public weights have been loaded. This process will receive one
        # bounded recording, emit one transcript, and terminate.
        sys.stdout.buffer.write(b"ASR_READY\n")
        sys.stdout.buffer.flush()
    audio = sys.stdin.buffer.read(480_045)
    validate_pcm(audio)
    with wave.open(io.BytesIO(audio), "rb") as wav:
        samples = np.frombuffer(wav.readframes(240000), dtype="<i2").astype(np.float32)/32768
    if model is None:
        model = load_model()
    segments, _ = model.transcribe(samples, beam_size=5, vad_filter=True, condition_on_previous_text=False,
                                   without_timestamps=True, max_new_tokens=96, temperature=0.0,
                                   # Fixed reviewed place vocabulary helps ASR
                                   # preserve proper names, not rental facts or
                                   # expected answers. Intent still consumes the
                                   # entire transcript and validates geography.
                                   hotwords=None)
    parts = []
    for segment in segments:
        # A token-bound truncation must not silently drop the last condition
        # of a composite request. Reject before intent/provider work instead.
        if len(segment.tokens) >= 96:
            raise ValueError("VOICE_TRANSCRIPT_TRUNCATED")
        parts.append(segment.text.strip())
    transcript = " ".join(parts).strip()
    if not 1 <= len(transcript) <= 2000:
        raise ValueError("VOICE_TRANSCRIPT_INVALID")
    sys.stdout.write(json.dumps(transcript, ensure_ascii=True))


if __name__ == "__main__":
    main()
