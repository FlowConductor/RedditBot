import json
import textwrap
import yaml


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def seconds_to_ass_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds * 100) % 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def group_words(word_timings, max_words=6, max_chars=80):
    groups = []
    current_words = []
    current_chars = 0
    group_start = None
    group_end = None

    for w in word_timings:
        wtext = w["text"]
        wlen = len(wtext)

        if current_words and (
            len(current_words) >= max_words
            or current_chars + wlen + 1 > max_chars
            or (wtext and wtext[-1] in ".!?")
        ):
            groups.append({
                "text": " ".join([x["text"] for x in current_words]),
                "start": group_start,
                "end": group_end,
            })
            current_words = []
            current_chars = 0
            group_start = None
            group_end = None

        current_words.append(w)
        current_chars += wlen + 1

        if group_start is None:
            group_start = w["start"]
        group_end = w["end"]

        if wtext and wtext[-1] in ".!?,":
            groups.append({
                "text": " ".join([x["text"] for x in current_words]),
                "start": group_start,
                "end": group_end,
            })
            current_words = []
            current_chars = 0
            group_start = None
            group_end = None

    if current_words:
        groups.append({
            "text": " ".join([x["text"] for x in current_words]),
            "start": group_start,
            "end": group_end,
        })

    return groups


def wrap_text(text, max_chars_per_line, max_lines):
    if len(text) <= max_chars_per_line:
        return [text]

    words = text.split()
    lines = []
    current_line = []

    for i, word in enumerate(words):
        candidate = " ".join(current_line + [word])
        if len(candidate) <= max_chars_per_line:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

            if len(lines) >= max_lines:
                remaining = " ".join(words[i:])
                if remaining:
                    if len(lines) == max_lines:
                        last = lines[-1]
                        combined = last + " " + remaining
                        wrapped = textwrap.wrap(combined, width=max_chars_per_line)
                        lines = wrapped[:max_lines]
                break

    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))

    return lines[:max_lines]


def generate_ass(word_timings, ass_file, config):
    sub_cfg = config["video"]["subtitle"]
    max_chars = sub_cfg["max_chars_per_line"]
    max_lines = sub_cfg["max_lines"]
    font_name = sub_cfg["font_name"]
    font_size = sub_cfg["font_size"]
    font_color = sub_cfg["font_color"]
    outline_color = sub_cfg["outline_color"]
    outline_width = sub_cfg["outline_width"]
    margin_v = sub_cfg["margin_v"]
    alignment = sub_cfg["alignment"]

    width = config["video"]["width"]
    height = config["video"]["height"]

    groups = group_words(word_timings, max_words=6, max_chars=max_chars * max_lines)

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{font_color},&H000000FF,{outline_color},&H00000000,1,0,0,0,100,100,0,0,1,{outline_width},0,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for i, group in enumerate(groups):
        text = group["text"]
        start = group["start"]
        end = group["end"]

        if i + 1 < len(groups):
            next_start = groups[i + 1]["start"]
            if end < next_start:
                end = next_start

        start_str = seconds_to_ass_time(start)
        end_str = seconds_to_ass_time(end)

        lines = wrap_text(text, max_chars, max_lines)
        ass_text = "\\N".join(lines)

        event_line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}"
        events.append(event_line)

    ass_content = ass_header + "\n".join(events) + "\n"

    with open(ass_file, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"    [SUB] Generated: {ass_file} ({len(events)} cues from {len(word_timings)} words)")
    return ass_file


if __name__ == "__main__":
    config = load_config()
    with open("output/test_timings.json", "r", encoding="utf-8") as f:
        timings = json.load(f)
    generate_ass(timings, "output/test.ass", config)
    with open("output/test.ass", "r", encoding="utf-8") as f:
        print(f.read())
