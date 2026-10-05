import os
import json
import yaml
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_credentials(config):
    client_secret_path = config["youtube"]["client_secret"]
    token_path = "token.json"

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def upload_video(video_path, title, reddit_url, config, tags=None):
    yt_cfg = config["youtube"]

    creds = get_credentials(config)
    service = build("youtube", "v3", credentials=creds)

    description = yt_cfg["description_template"].format(
        title=title,
        reddit_url=reddit_url,
    )

    if tags is None:
        tags = yt_cfg["tags"]

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": yt_cfg["category_id"],
        },
        "status": {
            "privacyStatus": yt_cfg["privacy_status"],
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    print(f"    [YT] Uploading: {video_path}")
    print(f"    [YT] Title: {title[:80]}")

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"    [YT] Progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"    [YT] Uploaded! URL: {video_url}")
    return video_id, video_url


if __name__ == "__main__":
    config = load_config()
    if not os.path.exists("output/test_video.mp4"):
        print("No test video found. Run video_maker.py first.")
        exit(1)

    video_id, url = upload_video(
        "output/test_video.mp4",
        "TEST - Reddit Story (DO NOT PUBLISH)",
        "https://reddit.com",
        config,
    )
    print(f"Video URL: {url}")
