"""Parse t.me/s/<channel> preview pages into posts: id, UTC time, edited flag, plain text."""
import html
import re

MSG_SPLIT = re.compile(r'(?=<div class="tgme_widget_message_wrap)')
POST_ID = re.compile(r'data-post="[^/"]+/(\d+)"')
TIME = re.compile(r'<time datetime="([^"]+)"')
TEXT = re.compile(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', re.S)
META = re.compile(r'<span class="tgme_widget_message_meta">(.*?)<a class="tgme_widget_message_date"', re.S)
BREAK = re.compile(r"<br\s*/?>")
TAG = re.compile(r"<[^>]+>")


def parse_page(page):
    """Posts on one preview page, oldest first. A post without text gets text ''."""
    posts = []
    for block in MSG_SPLIT.split(page)[1:]:
        pid, when = POST_ID.search(block), TIME.search(block)
        if not (pid and when):
            continue
        txt = TEXT.search(block)
        text = ""
        if txt:
            text = html.unescape(TAG.sub("", BREAK.sub(" ", txt.group(1))))
            text = re.sub(r"\s+", " ", text).strip()
        meta = META.search(block)
        posts.append({"id": int(pid.group(1)), "time_utc": when.group(1), "edited": bool(meta and "edited" in meta.group(1)),
                      "text": text})
    return sorted(posts, key=lambda p: p["id"])
