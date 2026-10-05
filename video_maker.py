import os
import subprocess
import glob
import json
import yaml


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_duration(file_path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def make_video(audio_path, output_path, config, bg_index=0, card_segments=None):
    bg_folder = config["video"]["background_folder"]
    width = config["video"]["width"]
    height = config["video"]["height"]
    fps = config["video"]["fps"]
    card_cfg = config["video"].get("reddit_card", {})
    card_height = card_cfg.get("height", 800)

    backgrounds = sorted(glob.glob(os.path.join(bg_folder, "bg_*.mp4")))
    if not backgrounds:
        raise RuntimeError(f"No background videos in {bg_folder}")

    bg_path = backgrounds[bg_index % len(backgrounds)]
    audio_duration = get_duration(audio_path)

    inputs = ["-stream_loop", "-1", "-i", bg_path, "-i", audio_path]

    bg_vf = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setsar=1,"
        f"drawbox=x=0:y=0:w={width}:h={card_height}:color=0x1A1A1B@1:t=fill"
        f"[bgcard]"
    )

    filter_parts = [bg_vf]

    prev_label = "bgcard"

    if card_segments:
        for i, seg in enumerate(card_segments):
            card_path = seg["path"]
            if not os.path.exists(card_path):
                continue
            inputs.extend(["-i", card_path])
            input_idx = 2 + i

            start = seg["start"]
            end = seg["end"]

            overlay_expr = (
                f"[{prev_label}][{input_idx}:v]"
                f"overlay=0:0:enable='between(t,{start},{end}')"
                f"[seg{i}]"
            )
            filter_parts.append(overlay_expr)
            prev_label = f"seg{i}"

    filter_complex = ";".join(filter_parts)

    audio_map_idx = 1
    if card_segments:
        audio_map_idx = 1

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev_label}]",
        "-map", f"{audio_map_idx}:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(audio_duration),
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"    [VID] BG: {os.path.basename(bg_path)} (index={bg_index})")
    print(f"    [VID] Cards: {len(card_segments) if card_segments else 0}")
    print(f"    [VID] Duration: {audio_duration:.1f}s")
    print(f"    [VID] Output: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"    [VID] FFmpeg stderr:\n{result.stderr[-3000:]}")
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Video not created: {output_path}")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"    [VID] Done! ({size_mb:.1f} MB)")
    return output_path
