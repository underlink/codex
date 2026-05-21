import asyncio
import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.error import TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("video-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
ALLOWED_HOSTS = (
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch",
    "www.fb.watch",
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_OVERRIDE", os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
MAX_VIDEO_MB = int(os.getenv("MAX_VIDEO_MB", "45"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "180"))
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "").strip()
YTDLP_COOKIES_CONTENT = os.getenv("YTDLP_COOKIES_CONTENT", "").strip()
YTDLP_COOKIES_BASE64 = os.getenv("YTDLP_COOKIES_BASE64", "").strip()
PORT = int(os.getenv("PORT", "0") or "0")
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server() -> None:
    if not PORT:
        return

    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server is listening on port %s", PORT)


def extract_supported_url(text: str) -> str | None:
    for match in URL_RE.findall(text):
        parsed = urlparse(match)
        host = parsed.netloc.lower()
        if host in ALLOWED_HOSTS or host.endswith(".instagram.com") or host.endswith(".facebook.com"):
            return match.rstrip(".,)")
    return None


def video_size_mb(path: Path) -> float:
    return path.stat().st_size / 1024 / 1024


def prepare_cookies_file(download_dir: Path) -> str | None:
    if YTDLP_COOKIES_FILE:
        return YTDLP_COOKIES_FILE

    content = YTDLP_COOKIES_CONTENT
    if YTDLP_COOKIES_BASE64:
        content = base64.b64decode(YTDLP_COOKIES_BASE64).decode("utf-8")

    if not content:
        return None

    cookies_path = download_dir / "cookies.txt"
    cookies_path.write_text(content, encoding="utf-8")
    return str(cookies_path)


def normalize_video(input_path: Path, download_dir: Path) -> Path:
    output_path = download_dir / f"{input_path.stem}-telegram.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        "scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return output_path


def download_video(url: str, download_dir: Path) -> tuple[Path, str | None]:
    output_template = str(download_dir / "download-%(id).40s.%(ext).10s")
    max_bytes = MAX_VIDEO_MB * 1024 * 1024

    ydl_opts = {
        "outtmpl": output_template,
        "format": (
            f"best[height<=1920][ext=mp4][filesize<{max_bytes}]/"
            f"bestvideo[height<=1920][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<=1920][ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "windowsfilenames": True,
        "trim_file_name": 80,
        "noplaylist": True,
        "geo_bypass": True,
        "retries": 3,
        "fragment_retries": 3,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": USER_AGENT,
            "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }

    cookies_file = prepare_cookies_file(download_dir)
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded = Path(ydl.prepare_filename(info))
        final_path = downloaded.with_suffix(".mp4")

        if final_path.exists():
            downloaded = final_path

        if not downloaded.exists():
            candidates = sorted(download_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True)
            if not candidates:
                raise FileNotFoundError("Відеофайл не було створено.")
            downloaded = candidates[0]

        normalized = normalize_video(downloaded, download_dir)
        return normalized, info.get("title")


def user_friendly_download_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "login" in text or "cookies" in text or "private" in text or "not available" in text:
        return (
            "Не вдалося дістати це відео. Facebook/Instagram просить авторизацію або обмежив доступ. "
            "Для таких посилань потрібен cookies-файл."
        )
    if "unsupported url" in text:
        return "Цей тип посилання не підтримався. Спробуйте відкрити відео і надіслати пряме посилання на reel/video."
    if "ffmpeg" in text:
        return "Відео завантажилось, але не вдалося підготувати його для Telegram."
    return "Не вдалося завантажити це відео. Спробуйте інше посилання або пряме посилання на reel/video."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Надішліть мені посилання на Instagram або Facebook відео, а я поверну відеофайл."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Просто вставте посилання на Instagram Reel або Facebook Reel/відео. "
        "Якщо сервіс просить авторизацію, додайте cookies-файл у налаштуваннях бота."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    url = extract_supported_url(message.text)
    if not url:
        await message.reply_text("Надішліть посилання з Instagram або Facebook.")
        return

    status = await message.reply_text("Завантажую відео...")
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)

    temp_dir = Path(tempfile.mkdtemp(prefix="tg-video-bot-"))
    try:
        video_path, title = await asyncio.wait_for(
            asyncio.to_thread(download_video, url, temp_dir),
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )

        size_mb = video_size_mb(video_path)
        if size_mb > MAX_VIDEO_MB:
            await status.edit_text(
                f"Відео завелике: {size_mb:.1f} MB. Ліміт зараз {MAX_VIDEO_MB} MB."
            )
            return

        caption = title[:900] if title else None
        with video_path.open("rb") as video:
            await message.reply_video(
                video=video,
                caption=caption,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300,
                connect_timeout=60,
                pool_timeout=60,
            )
        await status.delete()
    except asyncio.TimeoutError:
        await status.edit_text("Не встиг завантажити відео. Спробуйте ще раз або збільшіть timeout.")
    except DownloadError as exc:
        logger.warning("Download failed: %s", exc)
        await status.edit_text(user_friendly_download_error(exc))
    except subprocess.CalledProcessError as exc:
        logger.warning("Video normalization failed: %s", exc.stderr[-1000:] if exc.stderr else exc)
        await status.edit_text(user_friendly_download_error(exc))
    except TimedOut:
        await status.edit_text(
            "Відео завантажилось, але Telegram не встиг прийняти файл. "
            "Спробуйте ще раз або надішліть коротше відео."
        )
    except Exception as exc:
        logger.exception("Unexpected error")
        await status.edit_text(user_friendly_download_error(exc))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Заповніть TELEGRAM_BOT_TOKEN у файлі .env")

    start_health_server()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(120)
        .write_timeout(300)
        .connect_timeout(60)
        .pool_timeout(60)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
