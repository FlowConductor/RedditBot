import os
import subprocess
import sys
import glob
import yaml


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


SEARCH_QUERIES = [
    "minecraft parkour gameplay no copyright",
    "minecraft parkour gameplay free to use",
    "minecraft parkour gameplay creative commons",
    "minecraft gameplay no copyright background",
    "minecraft parkour speedrun gameplay",
]

DEFAULT_COUNT = 10


def download_backgrounds(config, count=DEFAULT_COUNT):
    bg_folder = config["video"]["background_folder"]
    os.makedirs(bg_folder, exist_ok=True)

    existing = sorted(glob.glob(os.path.join(bg_folder, "bg_*.mp4")))
    if len(existing) >= count:
        print(f"[BG] Already have {len(existing)} background videos.")
        return existing

    needed = count - len(existing)
    print(f"[BG] Need to download {needed} more background videos...")

    query = SEARCH_QUERIES[0]
    output_template = os.path.join(bg_folder, "bg_%(playlist_index)02d.mp4")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch{needed}:{query}",
        "-f", "mp4[height<=720]/mp4[height<=480]/mp4/best[height<=720]/best",
        "-o", output_template,
        "--no-warnings",
        "--no-check-certificates",
        "--socket-timeout", "30",
        "--retries", "3",
        "--throttled-rate", "100K",
    ]

    print(f"[BG] Searching: {query}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[BG] yt-dlp error: {result.stderr}")
        print(f"[BG] stdout: {result.stdout}")
        for alt_query in SEARCH_QUERIES[1:]:
            print(f"[BG] Trying alternative: {alt_query}")
            cmd[3] = f"ytsearch{needed}:{alt_query}"
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                break

    downloaded = sorted(glob.glob(os.path.join(bg_folder, "bg_*.mp4")))
    print(f"[BG] Total background videos: {len(downloaded)}")

    for f in downloaded:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"     {os.path.basename(f)} ({size_mb:.1f} MB)")

    return downloaded


def get_next_background(config, index):
    bg_folder = config["video"]["background_folder"]
    backgrounds = sorted(glob.glob(os.path.join(bg_folder, "bg_*.mp4")))

    if not backgrounds:
        raise RuntimeError(f"No background videos found in {bg_folder}. Run background_downloader first.")

    selected = backgrounds[index % len(backgrounds)]
    return selected


if __name__ == "__main__":
    config = load_config()
    count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT
    download_backgrounds(config, count)
