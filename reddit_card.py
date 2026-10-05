import os
import hashlib
import textwrap
import yaml
from PIL import Image, ImageDraw, ImageFont


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


DARK_BG = "#1A1A1B"
DARK_CARD_BG = "#272729"
DARK_BORDER = "#343536"
DARK_TEXT = "#D7DADC"
DARK_TEXT_MUTED = "#818384"
DARK_TITLE = "#D7DADC"
REDDIT_ORANGE = "#FF4500"
REDDIT_BLUE = "#0079D3"
UPVOTE_ORANGE = "#FF4500"
DOWNVOTE_BLUE = "#7193FF"

AVATAR_COLORS = [
    "#FF4500", "#0079D3", "#46D160", "#FFB000", "#7C7C7C",
    "#FF66AA", "#00A6A6", "#A06AFC", "#FF8717", "#0DD3BB",
]


def get_font(font_name, size, bold=False):
    if bold:
        paths = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arial.ttf"]
    else:
        paths = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text_lines(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = []
    for word in words:
        candidate = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def color_for_author(author):
    h = hashlib.md5(author.encode()).hexdigest()
    idx = int(h[:2], 16) % len(AVATAR_COLORS)
    return AVATAR_COLORS[idx]


def draw_vote_arrows(draw, x, y, font):
    up_font = get_font("Arial", 22, bold=True)
    score_font = get_font("Arial", 20, bold=True)
    draw.text((x, y), "^", fill=UPVOTE_ORANGE, font=up_font)
    return x + 24


def draw_header(draw, width, padding, subreddit, post_author, y):
    sub_font = get_font("Arial", 28, bold=True)
    sub_text = f"r/{subreddit}"
    draw.text((padding, y), sub_text, fill=DARK_TEXT, font=sub_font)

    bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_w = bbox[2] - bbox[0]

    info_font = get_font("Arial", 20)
    info_text = f"  -  Posted by u/{post_author}"
    draw.text((padding + sub_w + 8, y + 4), info_text, fill=DARK_TEXT_MUTED, font=info_font)
    y += 42

    score_font = get_font("Arial", 20, bold=True)
    arrow_font = get_font("Arial", 22, bold=True)
    draw.text((padding, y), "^", fill=UPVOTE_ORANGE, font=arrow_font)
    draw.text((padding + 24, y), "12.4k", fill=DARK_TEXT, font=score_font)
    draw.text((padding + 88, y), "v", fill=DOWNVOTE_BLUE, font=arrow_font)
    y += 30

    comment_icon_font = get_font("Arial", 18)
    draw.text((padding, y), "[-]  2.1k Comments", fill=DARK_TEXT_MUTED, font=comment_icon_font)
    y += 28

    return y


def draw_comment(draw, comment, padding, content_width, width, y, card_height, max_comment_lines=8):
    comment_font = get_font("Arial", 24)
    author_font = get_font("Arial", 20, bold=True)
    vote_font = get_font("Arial", 18, bold=True)
    arrow_font = get_font("Arial", 20, bold=True)
    meta_font = get_font("Arial", 18)

    avatar_r = 14
    cx = padding + avatar_r
    cy = y + avatar_r
    author = comment.get("author", "unknown")
    color = color_for_author(author)
    draw.ellipse([cx - avatar_r, cy - avatar_r, cx + avatar_r, cy + avatar_r], fill=color)

    initial = author[:1].upper() if author else "U"
    init_font = get_font("Arial", 14, bold=True)
    bbox = draw.textbbox((0, 0), initial, font=init_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - 2), initial, fill="white", font=init_font)

    author_x = padding + avatar_r * 2 + 10
    draw.text((author_x, y - 4), f"u/{author}", fill=DARK_TEXT, font=author_font)

    score = comment.get("score", f"{(comment.get('comment_index', 0) + 1) * 317}")
    points_text = f"  -  {score} points"
    draw.text((author_x, y + 20), points_text, fill=DARK_TEXT_MUTED, font=meta_font)

    bar_x = author_x
    bar_y = y + 44
    draw.text((bar_x, bar_y), "^", fill=UPVOTE_ORANGE, font=arrow_font)
    draw.text((bar_x + 20, bar_y + 1), "v", fill=DOWNVOTE_BLUE, font=arrow_font)
    draw.text((bar_x + 44, bar_y), "Reply", fill=DARK_TEXT_MUTED, font=meta_font)

    comment_x = author_x
    comment_y = bar_y + 28

    ctext = comment["text"]
    comment_lines = wrap_text_lines(ctext, comment_font, content_width - avatar_r * 2 - 10, draw)

    available_height = card_height - comment_y - 15
    line_height = 30
    max_lines = min(max_comment_lines, int(available_height / line_height))

    if len(comment_lines) > max_lines:
        max_lines -= 1

    for line in comment_lines[:max_lines]:
        draw.text((comment_x, comment_y), line, fill=DARK_TEXT, font=comment_font)
        comment_y += line_height

    if len(comment_lines) > max_lines:
        draw.text((comment_x, comment_y), "...", fill=DARK_TEXT_MUTED, font=comment_font)

    return comment_y + 15


def create_card(post, display_comment, config, output_path, card_height=None):
    card_cfg = config["video"]["reddit_card"]
    width = config["video"]["width"]
    if card_height is None:
        card_height = card_cfg["height"]

    img = Image.new("RGB", (width, card_height), DARK_BG)
    draw = ImageDraw.Draw(img)

    padding = 35
    content_width = width - padding * 2
    y = 20

    y = draw_header(draw, width, padding, post["subreddit"], post.get("author", "unknown"), y)

    title_font = get_font("Arial", card_cfg["title_font_size"], bold=True)
    title_lines = wrap_text_lines(post["title"], title_font, content_width, draw)
    for line in title_lines:
        draw.text((padding, y), line, fill=DARK_TITLE, font=title_font)
        y += card_cfg["title_font_size"] + 4
    y += 12

    draw.line([(padding, y), (width - padding, y)], fill=DARK_BORDER, width=2)
    y += 18

    if display_comment is not None:
        y = draw_comment(draw, display_comment, padding, content_width, width, y, card_height)

    img.save(output_path, "PNG")
    return output_path


def create_segment_cards(post, timed_segments, comments, config, output_dir, post_id):
    card_paths = []

    for i, seg in enumerate(timed_segments):
        if seg["type"] == "title":
            display_comment = None
        elif seg["type"] == "comment":
            comment_idx = seg.get("comment_index", 0)
            actual_comments = [c for c in comments if c["text"].strip() and len(c["text"].strip()) >= 20]
            comm_index_in_list = 0
            for j, c in enumerate(actual_comments):
                if c["text"].strip() in seg["text"] or seg["text"] in c["text"].strip():
                    comm_index_in_list = j
                    break
                comm_index_in_list = min(comment_idx, len(actual_comments) - 1)

            if comm_index_in_list < len(actual_comments):
                display_comment = actual_comments[comm_index_in_list]
                display_comment["comment_index"] = comm_index_in_list
            else:
                display_comment = None
        else:
            display_comment = None

        card_path = os.path.join(output_dir, f"card_{post_id}_{i}.png")
        create_card(post, display_comment, config, card_path)
        card_paths.append({
            "path": card_path,
            "start": seg["start"],
            "end": seg["end"],
            "type": seg["type"],
        })

    print(f"    [CARD] Generated {len(card_paths)} cards")
    return card_paths


if __name__ == "__main__":
    config = load_config()
    os.makedirs("output", exist_ok=True)

    post = {
        "title": "What industry has quietly fallen apart, while outsiders still think it's doing fine?",
        "subreddit": "AskReddit",
        "author": "test_user",
    }

    comments = [
        {"text": "Healthcare. The amount of paperwork and bureaucratic nonsense has tripled in the last decade. Doctors spend more time clicking boxes than actually treating patients.", "author": "doctor_throwaway", "score": "5.2k"},
        {"text": "Education. Teachers are burning out at record rates. Class sizes keep growing while budgets shrink. It's heartbreaking to watch.", "author": "teacher_life", "score": "3.1k"},
        {"text": "Journalism. Clickbait and outrage farming have replaced actual reporting. Most news outlets are just opinion factories now.", "author": "former_reporter", "score": "2.8k"},
    ]

    create_card(post, comments[0], config, "output/test_card_title.png")
    create_card(post, comments[1], config, "output/test_card_comment1.png")
    print("Done!")
