# Telegram video downloader bot

Бот приймає посилання на коротке вертикальне відео з Instagram або Facebook і надсилає відеофайл у відповідь.

> Використовуйте бота тільки для відео, які ви маєте право завантажувати та пересилати.

## Що вміє

- приймає URL з `instagram.com`, `facebook.com`, `fb.watch`, `m.facebook.com`;
- завантажує одне відео через `yt-dlp`;
- надсилає відео назад у Telegram;
- прибирає тимчасові файли після відправки;
- має обмеження розміру файлу, щоб не впиратися в ліміти Telegram.

## Встановлення

1. Створіть Telegram-бота через [@BotFather](https://t.me/BotFather) і отримайте токен.
2. Встановіть Python 3.11+.
3. Встановіть залежності:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Створіть файл `.env`:

```bash
cp .env.example .env
```

5. Впишіть токен у `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:your-token-here
```

## Запуск

```bash
source .venv/bin/activate
python bot.py
```

Після запуску надішліть боту посилання на Instagram Reel або Facebook Reel/відео.

## Запуск через Docker

```bash
cp .env.example .env
# заповніть TELEGRAM_BOT_TOKEN у .env
docker compose up -d --build
```

Переглянути логи:

```bash
docker compose logs -f bot
```

## Запуск в інтернеті

Бот уже готовий для роботи на сервері. Найпростіший варіант: орендувати VPS, встановити Docker і запустити:

```bash
docker compose up -d --build
```

Публічний домен для цього бота не потрібен: він працює через Telegram polling і сам забирає нові повідомлення з Telegram.

Детальна інструкція для VPS та хмарних worker-сервісів є у `DEPLOY.md`.

## Cookies для Instagram/Facebook

Деякі посилання можуть не завантажуватися без авторизації, особливо приватні, вікові або регіонально обмежені відео. Для таких випадків можна передати cookies-файл у форматі Netscape:

```env
YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
```

Найпростіше експортувати cookies з браузера через розширення на кшталт "Get cookies.txt LOCALLY".

## Налаштування

У `.env` можна змінити:

```env
MAX_VIDEO_MB=45
DOWNLOAD_TIMEOUT_SECONDS=180
```

За замовчуванням бот намагається тримати файл до 45 MB. Це консервативно і добре працює для більшості Telegram-ботів.
