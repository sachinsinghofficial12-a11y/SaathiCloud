
import queue
import sys
import numpy as np
import sounddevice as sd
import sherpa_onnx

# Model configuration
MODEL_DIR = "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"

SAMPLE_RATE = 16000
DEVICE_ID = 1
BLOCK_SIZE = 1600

audio_queue = queue.Queue(maxsize=50)


def audio_callback(indata, frames, time_info, status):
    if status:
        print("Audio status:", status)

    try:
        audio_queue.put_nowait(indata[:, 0].copy())
    except queue.Full:
        pass


def main():
    print("Saathi Wake Word starting...")

    kws = sherpa_onnx.KeywordSpotter(
        tokens=f"{MODEL_DIR}/tokens.txt",
        encoder=f"{MODEL_DIR}/encoder-epoch-13-avg-2-chunk-16-left-64.onnx",
        decoder=f"{MODEL_DIR}/decoder-epoch-13-avg-2-chunk-16-left-64.onnx",
        joiner=f"{MODEL_DIR}/joiner-epoch-13-avg-2-chunk-16-left-64.onnx",
        keywords_file="saathi_keyword_tokens.txt",
        num_threads=2,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        max_active_paths=4,
        keywords_score=2.0,
        keywords_threshold=0.25,
        num_trailing_blanks=1,
        provider="cpu",
    )

    stream = kws.create_stream()

    print("Microphone:", DEVICE_ID)
    print("Listening for SAATHI...")
    print("Press Ctrl+C to stop.\n")

    with sd.InputStream(
        device=DEVICE_ID,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
        callback=audio_callback,
    ):
        while True:
            samples = audio_queue.get()

            stream.accept_waveform(
                SAMPLE_RATE,
                np.asarray(samples, dtype=np.float32),
            )

            while kws.is_ready(stream):
                kws.decode_stream(stream)

            result = kws.get_result(stream)

            if result:
                print("\nSAATHI DETECTED!")
                print("Detection result:", result)
                print("Listening again...\n")
                kws.reset_stream(stream)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaathi Wake Word stopped.")
    except Exception as error:
        print("\nError:", error)
        sys.exit(1)
