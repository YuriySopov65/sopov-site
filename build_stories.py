"""Build the home page with the two scheduled rubrics for one Moscow date."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
MOSCOW = timezone(timedelta(hours=3))
RUBRICS = {
    "sopov_lider": (r"как не (?:нужно|надо) управлять", "Как не нужно управлять", "Из практики управления"),
    "sopov_praktika": (r"с мир[ау] по нитке", "С миру по нитке…", "Из практики продаж"),
}


def read_story(channel, pattern, day):
    request = Request(f"https://t.me/s/{channel}", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        feed = BeautifulSoup(response.read(), "html.parser")

    candidates = []
    for post in feed.select(".tgme_widget_message[data-post]"):
        post_id = re.fullmatch(rf"{re.escape(channel)}/(\d+)", post["data-post"])
        message = post.select_one(".tgme_widget_message_text")
        timestamp = post.select_one(".tgme_widget_message_date time[datetime]")
        if not post_id or not message or not timestamp:
            continue
        published = datetime.fromisoformat(timestamp["datetime"]).astimezone(MOSCOW)
        if published.date() != day:
            continue

        for link in message.find_all("a"):
            if re.match(r"^(источник|отзыв сотрудника|рассказ станислава кима)(?:\s|$)", link.get_text(strip=True), re.I):
                link.decompose()
        for br in message.find_all("br"):
            br.replace_with("\n")
        lines = [re.sub(r"\s+", " ", part).strip() for part in message.get_text().splitlines()]
        lines = [part for part in lines if part]
        if len(lines) > 1 and re.fullmatch(rf"[^\w]*{pattern}[.!…\s]*", lines[0], re.I):
            candidates.append((published, int(post_id[1]), lines[1:]))
    if not candidates:
        raise RuntimeError(f"No {channel} story for {day.isoformat()}; keep the last deployed page")
    _, post_id, lines = min(candidates, key=lambda item: (item[0], item[1]))
    return post_id, lines


def replace_story(document, day, channel, pattern, rubric, fallback_title):
    post_id, lines = read_story(channel, pattern, day)
    story = document.select_one(f'article[data-channel="{channel}"]')
    title = fallback_title
    if len(lines) > 1 and len(lines[0]) <= 100:
        title, *lines = lines

    story.clear()
    label = document.new_tag("p", attrs={"class": "rubric"})
    label.string = rubric
    label.append(" · ")
    stamp = document.new_tag("time", datetime=day.isoformat())
    stamp.string = day.strftime("%d.%m.%Y")
    label.append(stamp)
    story.append(label)
    heading = document.new_tag("h3")
    heading.string = title
    story.append(heading)
    for line in lines:
        paragraph = document.new_tag("p")
        paragraph.string = line
        story.append(paragraph)
    link = document.new_tag("a", href=f"https://t.me/{channel}/{post_id}", attrs={"class": "text-link"})
    link.string = "Открыть исходный выпуск ↗"
    story.append(link)
    print(f"{day.isoformat()} {channel}: selected post {post_id}")


def build(output, day):
    page = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
    if day != date(2026, 11, 23):
        for channel, rubric in RUBRICS.items():
            replace_story(page, day, channel, *rubric)

    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(str(page), encoding="utf-8")


if __name__ == "__main__":
    requested_day = sys.argv[2] if len(sys.argv) > 2 else ""
    day = date.fromisoformat(requested_day) if requested_day else datetime.now(MOSCOW).date()
    build(Path(sys.argv[1]), day)
