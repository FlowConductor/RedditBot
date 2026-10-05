import asyncio
import edge_tts
import json
import os
import subprocess
import yaml


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def generate_tts(text, output_mp3, word_timings_file, config):
    tts_cfg = config["tts"]
    voice = tts_cfg["voice"]
    rate = tts_cfg["rate"]
    volume = tts_cfg["volume"]

    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, boundary="WordBoundary")

    word_timings = []

    with open(output_mp3, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                offset_s = chunk["offset"] / 10000000
                duration_s = chunk["duration"] / 10000000
                word_timings.append({
                    "text": chunk["text"].strip(),
                    "start": round(offset_s, 3),
                    "end": round(offset_s + duration_s, 3),
                })

    with open(word_timings_file, "w", encoding="utf-8") as f:
        json.dump(word_timings, f, indent=2, ensure_ascii=False)

    return word_timings


def get_audio_duration(mp3_path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", mp3_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def match_segments_to_timings(segments, word_timings, timing_offset=0.0):
    word_idx = 0
    result = []

    for seg in segments:
        seg_words = seg["text"].split()
        seg_word_count = len(seg_words)

        if word_idx >= len(word_timings):
            if result:
                prev_end = result[-1]["end"]
            else:
                prev_end = 0
            result.append({
                "type": seg["type"],
                "text": seg["text"],
                "start": prev_end,
                "end": prev_end,
                "comment_index": seg.get("comment_index"),
            })
            continue

        seg_start = word_timings[word_idx]["start"]

        skip = min(seg_word_count, len(word_timings) - word_idx)
        word_idx += skip - 1

        if word_idx < len(word_timings):
            seg_end = word_timings[word_idx]["end"]
        else:
            seg_end = word_timings[-1]["end"]

        word_idx += 1

        result.append({
            "type": seg["type"],
            "text": seg["text"],
            "start": round(seg_start, 3),
            "end": round(seg_end, 3),
            "comment_index": seg.get("comment_index"),
        })

    for i in range(len(result) - 1):
        if result[i]["end"] < result[i + 1]["start"]:
            result[i]["end"] = result[i + 1]["start"]

    # Compensate for MP3/edge-tts playback delay: cards were switching
    # slightly before the audio actually played.
    if timing_offset:
        for seg in result:
            seg["start"] = round(seg["start"] + timing_offset, 3)
            seg["end"] = round(seg["end"] + timing_offset, 3)

    # First card must appear immediately, otherwise the drawbox area
    # shows as a black bar until the first word starts.
    if result:
        result[0]["start"] = 0

    return result


def generate_speech(text, output_mp3, word_timings_file, config):
    asyncio.run(generate_tts(text, output_mp3, word_timings_file, config))

    if not os.path.exists(output_mp3):
        raise RuntimeError(f"TTS failed: {output_mp3} not created")

    duration = get_audio_duration(output_mp3)
    print(f"    [TTS] Audio: {output_mp3} ({duration:.1f}s)")

    if os.path.exists(word_timings_file):
        with open(word_timings_file, "r", encoding="utf-8") as f:
            timings = json.load(f)
        print(f"    [TTS] Word timings: {len(timings)} words")
        return duration, timings

    return duration, []


if __name__ == "__main__":
    config = load_config()
    os.makedirs("output", exist_ok=True)
    text = "Hello, this is a test. Let's see how it works. I hope this is good."
    asyncio.run(generate_tts(
        text, "output/test.mp3", "output/test_timings.json", config
    ))
    print("Done!")
