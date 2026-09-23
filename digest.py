"""Tổng hợp tin từ các trang trong sources.txt rồi gửi qua Email và/hoặc Zalo.

Cấu hình qua biến môi trường (đặt trong GitHub Secrets):
  ANTHROPIC_API_KEY   - khóa API Claude để viết bản tóm tắt (không có thì chỉ liệt kê tiêu đề)
  SMTP_USER, SMTP_PASSWORD, EMAIL_TO   - gửi email (Gmail: dùng "Mật khẩu ứng dụng")
  SMTP_HOST (mặc định smtp.gmail.com), SMTP_PORT (mặc định 465)
  ZALO_BOT_TOKEN, ZALO_CHAT_ID         - gửi qua Zalo Bot
"""

import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

VN_TZ = timezone(timedelta(hours=7))
USER_AGENT = "Mozilla/5.0 (compatible; DailyDigestBot/1.0)"
MAX_ITEMS_PER_FEED = 15
MAX_CHARS_PER_PAGE = 20000
ZALO_MAX_CHARS = 2000


def load_sources(path="sources.txt"):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def fetch_source(url):
    """Trả về (tiêu đề nguồn, nội dung văn bản, danh sách tiêu đề bài)."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    feed = feedparser.parse(resp.content)
    if feed.entries:
        entries = feed.entries[:MAX_ITEMS_PER_FEED]
        text = "\n".join(
            f"- {e.get('title', '')}: "
            f"{BeautifulSoup(e.get('summary', ''), 'html.parser').get_text(' ', strip=True)} "
            f"({e.get('link', '')})"
            for e in entries
        )
        headlines = [(e.get("title", ""), e.get("link", "")) for e in entries]
        return feed.feed.get("title", url), text, headlines

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else url
    text = soup.get_text("\n", strip=True)
    if len(text) > MAX_CHARS_PER_PAGE:
        print(f"[cảnh báo] {url}: nội dung dài {len(text)} ký tự, chỉ lấy {MAX_CHARS_PER_PAGE} ký tự đầu")
        text = text[:MAX_CHARS_PER_PAGE]
    headlines = [
        (h.get_text(strip=True), "") for h in soup.find_all(["h1", "h2", "h3"])[:MAX_ITEMS_PER_FEED]
    ]
    return title, text, headlines


def summarize_with_claude(collected, session_label):
    import anthropic

    client = anthropic.Anthropic()
    docs = "\n\n".join(
        f"<source url=\"{url}\" title=\"{title}\">\n{text}\n</source>"
        for url, title, text, _ in collected
    )
    prompt = (
        f"Dưới đây là nội dung mới nhất từ các trang tin tôi theo dõi ({session_label}).\n\n"
        f"{docs}\n\n"
        "Hãy viết bản tin tổng hợp bằng tiếng Việt, ngắn gọn, dễ đọc trên điện thoại:\n"
        "- Mở đầu bằng 3-5 điểm nổi bật nhất.\n"
        "- Sau đó nhóm tin theo chủ đề, mỗi tin 1-2 câu, kèm đường link nếu có.\n"
        "- Gộp các tin trùng nhau giữa các trang.\n"
        "- Chỉ dùng thông tin có trong nội dung trên, không bịa thêm.\n"
        "- Viết dạng văn bản thuần (không dùng Markdown như ** hay #)."
    )
    with client.beta.messages.stream(
        model="claude-opus-5",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude từ chối yêu cầu tóm tắt")
    return "".join(b.text for b in message.content if b.type == "text").strip()


def headlines_only(collected):
    parts = []
    for url, title, _, headlines in collected:
        parts.append(f"== {title} ==")
        parts += [f"- {t} {link}".rstrip() for t, link in headlines if t]
        parts.append("")
    return "\n".join(parts).strip()


def send_email(subject, body):
    user, password, to = (os.getenv(k) for k in ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (user and password and to):
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=60) as smtp:
        smtp.login(user, password)
        smtp.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    print(f"Đã gửi email tới {to}")
    return True


def send_zalo(text):
    token, chat_id = os.getenv("ZALO_BOT_TOKEN"), os.getenv("ZALO_CHAT_ID")
    if not (token and chat_id):
        return False
    url = f"https://bot-api.zaloplatforms.com/bot{token}/sendMessage"
    chunks = [text[i : i + ZALO_MAX_CHARS] for i in range(0, len(text), ZALO_MAX_CHARS)]
    for chunk in chunks:
        r = requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok", True):
            raise RuntimeError(f"Zalo trả lỗi: {data}")
    print(f"Đã gửi Zalo ({len(chunks)} tin nhắn)")
    return True


def main():
    now = datetime.now(VN_TZ)
    session_label = f"bản tin {now:%H:%M} ngày {now:%d/%m/%Y}"

    collected, errors = [], []
    for url in load_sources():
        try:
            title, text, headlines = fetch_source(url)
            collected.append((url, title, text, headlines))
        except Exception as e:  # một trang lỗi không làm hỏng cả bản tin
            errors.append(f"{url}: {e}")
            print(f"[lỗi] {url}: {e}")

    if not collected:
        print("Không lấy được trang nào.")
        sys.exit(1)

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            body = summarize_with_claude(collected, session_label)
        except Exception as e:
            print(f"[lỗi] Tóm tắt bằng Claude thất bại, dùng danh sách tiêu đề: {e}")
            body = headlines_only(collected)
    else:
        body = headlines_only(collected)

    if errors:
        body += "\n\n(Không truy cập được: " + "; ".join(errors) + ")"

    subject = f"Tổng hợp tin - {session_label}"
    full = f"{subject}\n\n{body}"
    print(full)

    sent_email = send_email(subject, body)
    sent_zalo = send_zalo(full)
    if not (sent_email or sent_zalo):
        print("Chưa cấu hình kênh gửi nào (Email hoặc Zalo) - chỉ in ra màn hình.")


if __name__ == "__main__":
    main()
