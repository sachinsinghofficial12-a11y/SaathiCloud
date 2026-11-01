import io
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import sherpa_onnx
import pyttsx3
from dotenv import load_dotenv
from groq import Groq

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
MODEL = BASE / "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
KEYWORDS = BASE / "saathi_keyword_tokens.txt"
load_dotenv(ROOT / ".env")

SAMPLE_RATE = 16000
MIC_DEVICE = 1
BACKEND = "https://saathicloud-1.onrender.com/command"
conversation_id = None


def speak(engine, message):
    print("Saathi:", message)
    engine.say(str(message))
    engine.runAndWait()


def make_tts():
    engine = pyttsx3.init()
    engine.setProperty("rate", 170)
    engine.setProperty("volume", 1.0)
    voices = engine.getProperty("voices")
    for voice in voices:
        name = (voice.name + " " + voice.id).lower()
        if any(word in name for word in ("zira", "female", "woman", "heera", "kalpana")):
            engine.setProperty("voice", voice.id)
            print("Selected voice:", voice.name)
            break
    else:
        print("Female Windows voice not found; using default installed voice.")
    return engine


def build_spotter():
    return sherpa_onnx.KeywordSpotter(
        tokens=str(MODEL / "tokens.txt"),
        encoder=str(MODEL / "encoder-epoch-13-avg-2-chunk-16-left-64.onnx"),
        decoder=str(MODEL / "decoder-epoch-13-avg-2-chunk-16-left-64.onnx"),
        joiner=str(MODEL / "joiner-epoch-13-avg-2-chunk-16-left-64.onnx"),
        keywords_file=str(KEYWORDS),
        num_threads=2,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        max_active_paths=4,
        keywords_score=2.0,
        keywords_threshold=0.25,
        num_trailing_blanks=1,
        provider="cpu",
    )


def record_until_silence():
    print("Boliye... (maximum 15 seconds)")
    chunks = []
    started = False
    last_voice = None
    start = time.monotonic()
    with sd.InputStream(device=MIC_DEVICE, samplerate=SAMPLE_RATE,
                        channels=1, dtype="float32", blocksize=1600) as mic:
        while time.monotonic() - start < 15:
            data, overflow = mic.read(1600)
            samples = data[:, 0].copy()
            peak = float(np.max(np.abs(samples)))
            now = time.monotonic()
            if peak > 0.012:
                started = True
                last_voice = now
            if started:
                chunks.append(samples)
            if started and last_voice and now - last_voice > 1.4:
                break
    if not chunks:
        return None
    audio = np.concatenate(chunks)
    pcm = np.clip(audio * 32767, -32768, 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def transcribe(client, audio):
    result = client.audio.transcriptions.create(
        file=("saathi_command.wav", audio),
        model="whisper-large-v3-turbo",
        response_format="text",
        language="hi",
    )
    return result.strip() if isinstance(result, str) else str(result.text).strip()


def send_to_saathi(api_key, command):
    global conversation_id
    payload = {"command": command}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = requests.post(
        BACKEND,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    conversation_id = data.get("conversation_id", conversation_id)
    return data.get("reply") or data.get("error") or "Abhi jawab nahi mil paya."


def main():
    api_key = os.getenv("SAATHI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or not groq_key:
        raise RuntimeError("Project ke main folder wali .env file mein SAATHI_API_KEY aur GROQ_API_KEY check karein.")
    for file in (MODEL / "tokens.txt", KEYWORDS):
        if not file.exists():
            raise FileNotFoundError(f"File nahi mili: {file}")

    tts = make_tts()
    groq = Groq(api_key=groq_key)
    kws = build_spotter()
    stream = kws.create_stream()

    print("Mic device:", MIC_DEVICE)
    print("Saathi wake-word assistant is running. Ctrl+C to stop.")
    speak(tts, "Saathi ready hai, Sachin Sir.")

    def callback(indata, frames, time_info, status):
        if status:
            print("Mic status:", status)
        try:
            audio_queue.put_nowait(indata[:, 0].copy())
        except Exception:
            pass

    import queue
    audio_queue = queue.Queue(maxsize=60)

    with sd.InputStream(device=MIC_DEVICE, samplerate=SAMPLE_RATE,
                        channels=1, dtype="float32", blocksize=1600,
                        callback=callback):
        while True:
            samples = audio_queue.get()
            stream.accept_waveform(SAMPLE_RATE, np.asarray(samples, dtype=np.float32))
            while kws.is_ready(stream):
                kws.decode_stream(stream)
            result = kws.get_result(stream)
            if result and "SAATHI" in result.upper():
                print("\nWake word detected!")
                kws.reset_stream(stream)
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        break
                speak(tts, "Ji Sachin Sir, boliye!")
                try:
                    audio = record_until_silence()
                    if not audio:
                        speak(tts, "Aapki awaaz sunai nahi di. Dobara Saathi boliye.")
                    else:
                        print("Voice ko text mein badal raha hoon...")
                        command = transcribe(groq, audio)
                        print("Aap:", command)
                        if command:
                            speak(tts, "Ji, ek second.")
                            answer = send_to_saathi(api_key, command)
                            speak(tts, answer)
                        else:
                            speak(tts, "Command samajh nahi aayi.")
                except requests.HTTPError as exc:
                    print("Server error:", exc.response.text[:400] if exc.response else str(exc))
                    speak(tts, "Server se connect nahi ho pa raha.")
                except Exception as exc:
                    print("Command error:", repr(exc))
                    speak(tts, "Maaf kijiye, command process nahi ho paayi.")
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        break
                stream = kws.create_stream()
                print("\nListening again for SAATHI...\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaathi stopped.")
    except Exception as exc:
        print("\nStartup error:", repr(exc))
        sys.exit(1)
