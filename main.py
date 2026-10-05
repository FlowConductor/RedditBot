import os
import sys
import json
import shutil
import argparse
import yaml
import re

from reddit_fetcher import fetch_posts, fetch_post_with_comments, mark_post_used
from tts_engine import generate_speech, match_segments_to_timings
from reddit_card import create_segment_cards
from video_maker import make_video
from background_downloader import download_backgrounds


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clean_text(text):
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("\n\n", ". ")
    text = text.replace("\n", " ")
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def process_single_post(post, config, index, bg_index, skip_upload=False):
    post_id = post["id"]
    title = post["title"]
    reddit_url = post["url"]

    post = fetch_post_with_comments(post, config)

    full_text = clean_text(post.get("story_text", title))
    segments = post.get("segments", [])
    comments = post.get("comments", [])

    print(f"\n{'='*60}")
    print(f"  [{index+1}] r/{post['subreddit']}")
    print(f"  Title: {title[:80]}")
    print(f"  Comments: {len(comments)}")
    print(f"  Segments: {len(segments)}")
    print(f"  Story text: {len(full_text)} chars, ~{len(full_text.split())} words")
    print(f"  URL: {reddit_url}")
    print(f"{'='*60}")

    output_folder = config["output"]["folder"]
    os.makedirs(output_folder, exist_ok=True)

    audio_path = os.path.join(output_folder, f"story_{post_id}.mp3")
    timings_path = os.path.join(output_folder, f"timings_{post_id}.json")
    video_path = os.path.join(output_folder, f"video_{post_id}.mp4")

    print(f"\n  [1/4] Generating speech...")
    duration, word_timings = generate_speech(full_text, audio_path, timings_path, config)

    print(f"  [2/4] Matching segments to audio timings...")
    timing_offset = config["reddit"].get("timing_offset_sec", 0.2)
    timed_segments = match_segments_to_timings(segments, word_timings, timing_offset)
    print(f"    Matched {len(timed_segments)} segments:")
    for seg in timed_segments:
        print(f"    [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['type']}: {seg['text'][:60]}")

    print(f"  [3/4] Generating Reddit cards...")
    card_segments = create_segment_cards(post, timed_segments, comments, config, output_folder, post_id)

    print(f"  [4/4] Making video...")
    make_video(audio_path, video_path, config, bg_index=bg_index, card_segments=card_segments)

    if not skip_upload:
        print(f"  [5/5] Uploading to YouTube...")
        try:
            from youtube_uploader import upload_video
            video_title = f"{title[:80]} | Reddit Story"
            video_id, yt_url = upload_video(video_path, video_title, reddit_url, config)

            uploaded_folder = config["output"]["uploaded_folder"]
            os.makedirs(uploaded_folder, exist_ok=True)
            shutil.move(video_path, os.path.join(uploaded_folder, f"video_{post_id}.mp4"))

            metadata = {
                "post_id": post_id,
                "title": title,
                "reddit_url": reddit_url,
                "youtube_url": yt_url,
                "youtube_id": video_id,
                "duration": duration,
            }
            with open(os.path.join(uploaded_folder, f"meta_{post_id}.json"), "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            print(f"\n  [OK] Published: {yt_url}")
        except Exception as e:
            print(f"  [!] Upload failed: {e}")
            print(f"  [!] Video saved at: {video_path}")
    else:
        print(f"  [5/5] Upload skipped (--no-upload)")
        print(f"\n  [OK] Video ready: {video_path}")

    mark_post_used(post_id, config)

    for f in [audio_path, timings_path]:
        if os.path.exists(f):
            os.remove(f)

    for seg in card_segments:
        if os.path.exists(seg["path"]):
            os.remove(seg["path"])

    print(f"  [CLEAN] Temporary files removed.")
    return video_path


def main():
    parser = argparse.ArgumentParser(description="Reddit Shorts Automation")
    parser.add_argument("--count", type=int, default=1, help="Number of videos to produce")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--download-bg", type=int, metavar="N", help="Download N background videos and exit")
    parser.add_argument("--list", action="store_true", help="List available Reddit posts and exit")
    args = parser.parse_args()

    config = load_config()

    if args.download_bg:
        download_backgrounds(config, args.download_bg)
        return

    print("\n  Reddit Shorts Automation")
    print(f"  Mode: {'NO UPLOAD' if args.no_upload else 'AUTO UPLOAD'}")
    print(f"  Count: {args.count}")

    bg_index = 0
    bg_folder = config["video"]["background_folder"]
    existing_bgs = []
    if os.path.isdir(bg_folder):
        import glob
        existing_bgs = sorted(glob.glob(os.path.join(bg_folder, "bg_*.mp4")))

    if not existing_bgs:
        print("\n  [!] No background videos found. Downloading 10...")
        download_backgrounds(config, 10)

    if args.list:
        posts = fetch_posts(config, count=10)
        print(f"\n  Available posts ({len(posts)}):")
        for i, p in enumerate(posts):
            print(f"  [{i+1}] r/{p['subreddit']} | {p['title'][:70]}")
        return

    posts = fetch_posts(config, count=args.count)

    if not posts:
        print("\n  [!] No suitable posts found. Try again later or adjust config.yaml filters.")
        return

    print(f"\n  Found {len(posts)} posts to process.")

    for i, post in enumerate(posts):
        try:
            process_single_post(post, config, i, bg_index, skip_upload=args.no_upload)
            bg_index += 1
        except Exception as e:
            print(f"\n  [!] Error processing post {post['id']}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n  Done! Processed {len(posts)} posts.")


if __name__ == "__main__":
    main()
