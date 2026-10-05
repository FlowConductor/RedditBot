import json
import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import yaml


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_used_posts(used_posts_file):
    if os.path.exists(used_posts_file):
        with open(used_posts_file, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_used_posts(used_posts_file, used_posts):
    with open(used_posts_file, "w", encoding="utf-8") as f:
        json.dump(list(used_posts), f, indent=2)


RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/atom+xml, application/xml, text/xml",
}


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


def fetch_rss(url, retries=5):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=RSS_HEADERS, timeout=15)
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s... (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait = 30 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s... (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            raise
    print(f"    Failed after {retries} retries (rate limited)")
    return None


def parse_rss_entries(xml_text):
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ns):
        title_elem = entry.find("atom:title", ns)
        link_elem = entry.find("atom:link", ns)
        content_elem = entry.find("atom:content", ns)
        author_elem = entry.find("atom:author/atom:name", ns)

        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
        link = link_elem.get("href", "") if link_elem is not None else ""
        content_html = content_elem.text if content_elem is not None and content_elem.text else ""
        author = author_elem.text.strip() if author_elem is not None and author_elem.text else ""

        content_text = BeautifulSoup(content_html, "html.parser").get_text(strip=True) if content_html else ""

        entries.append({
            "title": title,
            "link": link,
            "content": content_text,
            "author": author,
        })
    return entries


def fetch_subreddit_posts(subreddit, config):
    limit = config["reddit"]["fetch_count"]
    url = f"https://www.reddit.com/r/{subreddit}/hot/.rss?limit={limit}"

    xml_text = fetch_rss(url)
    if not xml_text:
        return []

    entries = parse_rss_entries(xml_text)
    posts = []

    for e in entries:
        link = e["link"]
        match = re.search(r"/comments/([a-z0-9]+)/", link)
        post_id = match.group(1) if match else ""
        if not post_id:
            continue

        title = e["title"]
        content = e["content"]

        selftext = ""
        if "<!-- SC_OFF -->" in content:
            sc_match = re.search(r"<!-- SC_OFF -->(.*?)<!-- SC_ON -->", content, re.DOTALL)
            if sc_match:
                selftext = BeautifulSoup(sc_match.group(1), "html.parser").get_text(strip=True)
        else:
            if "[link]" not in content and "[comments]" not in content and len(content) > 50:
                selftext = content

        posts.append({
            "id": post_id,
            "title": title,
            "selftext": selftext,
            "score": 0,
            "permalink": link.replace("https://www.reddit.com", ""),
            "subreddit": subreddit,
            "url": link,
        })

    return posts


def fetch_comments(post_url, limit=10):
    rss_url = post_url.rstrip("/") + f"/.rss?limit={limit}"
    xml_text = fetch_rss(rss_url)
    if not xml_text:
        return []

    entries = parse_rss_entries(xml_text)
    comments = []

    for e in entries:
        if "/comments/" not in e["link"]:
            continue

        is_post = e["link"].rstrip("/").split("/")[-1] == re.search(r"/comments/([a-z0-9]+)/", e["link"]).group(1) if re.search(r"/comments/([a-z0-9]+)/", e["link"]) else False

        comment_match = re.search(r"/comments/[a-z0-9]+/[^/]*/([a-z0-9]+)", e["link"])
        if comment_match:
            comment_text = e["content"]
            if comment_text and "[link]" not in comment_text and "[comments]" not in comment_text:
                author = e["author"].replace("/u/", "") if e["author"] else ""
                comments.append({
                    "text": comment_text,
                    "author": author,
                })

    return comments


def build_story_text(post, comments, config):
    target_duration = config["reddit"].get("target_duration_sec", 60)
    words_per_sec = 2.5
    target_words = int(target_duration * words_per_sec)

    segments = []
    total_words = 0

    title_text = post["title"]
    if post.get("selftext"):
        title_text += ". " + post["selftext"]
    title_text = clean_text(title_text)

    segments.append({"type": "title", "text": title_text})
    total_words += len(title_text.split())

    for c in comments:
        ctext = c["text"].strip()
        if not ctext or len(ctext) < 20:
            continue
        if total_words >= target_words:
            break
        segments.append({"type": "comment", "text": ctext, "comment_index": len(segments)})
        total_words += len(ctext.split())

    full_text = ". ".join([s["text"] for s in segments])
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    return full_text, segments


def filter_posts(posts, config):
    used = load_used_posts(config["output"]["used_posts_file"])
    banned_keywords = ["moderator", "looking for", "megathread", "weekly thread", "monthly thread"]
    reddit_cfg = config["reddit"]

    filtered = []
    for p in posts:
        if p["id"] in used:
            continue
        if not p["id"]:
            continue

        title_lower = p["title"].lower()
        if any(kw in title_lower for kw in banned_keywords):
            continue

        filtered.append(p)

    return filtered


def fetch_posts(config, count=1):
    all_filtered = []
    for sub in config["subreddits"]:
        if len(all_filtered) >= count:
            break
        try:
            print(f"  [Reddit] Fetching r/{sub}...")
            posts = fetch_subreddit_posts(sub, config)
            filtered = filter_posts(posts, config)
            print(f"  [Reddit] r/{sub}: {len(filtered)} valid posts")
            all_filtered.extend(filtered)
        except Exception as e:
            print(f"[!] r/{sub} fetch error: {e}")
        time.sleep(8)

    return all_filtered[:count]


def fetch_post_with_comments(post, config):
    comment_limit = config["reddit"].get("comment_count", 15)

    wait_before_comments = config["reddit"].get("wait_before_comments_sec", 60)
    print(f"  [Reddit] Waiting {wait_before_comments}s before fetching comments...")
    time.sleep(wait_before_comments)

    print(f"  [Reddit] Fetching comments for {post['id']}...")
    comments = fetch_comments(post["url"], limit=comment_limit)
    print(f"  [Reddit] Got {len(comments)} comments")

    story_text, segments = build_story_text(post, comments, config)
    post["story_text"] = story_text
    post["comments"] = comments
    post["segments"] = segments

    return post


def mark_post_used(post_id, config):
    used_posts_file = config["output"]["used_posts_file"]
    used = load_used_posts(used_posts_file)
    used.add(post_id)
    save_used_posts(used_posts_file, used)


if __name__ == "__main__":
    config = load_config()
    posts = fetch_posts(config, count=3)
    for p in posts:
        p = fetch_post_with_comments(p, config)
        print(f"\nr/{p['subreddit']}: {p['title'][:80]}")
        print(f"  Comments: {len(p['comments'])}")
        print(f"  Story text ({len(p['story_text'])} chars, ~{len(p['story_text'].split())} words):")
        print(f"  {p['story_text'][:500]}")
        print()
        time.sleep(8)
