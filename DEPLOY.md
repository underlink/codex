# Деплой Telegram-бота в інтернеті

Бот не потребує сайту, домену чи webhook. Він працює через polling: сервер запускає процес, процес постійно слухає Telegram і відповідає на повідомлення.

## Варіант 1: VPS + Docker Compose

Підійде будь-який VPS з Ubuntu: Hetzner, DigitalOcean, AWS Lightsail, Oracle Cloud, Contabo тощо.

### 1. Підготуйте сервер

Встановіть Docker і Docker Compose:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
```

### 2. Завантажте проєкт на сервер

Якщо проєкт у GitHub:

```bash
git clone https://github.com/your-name/your-repo.git
cd your-repo
```

Або просто скопіюйте папку проєкту на сервер через SFTP/SCP.

### 3. Створіть `.env`

```bash
cp .env.example .env
nano .env
```

Мінімально потрібно:

```env
TELEGRAM_BOT_TOKEN=123456:your-token-here
```

### 4. Запустіть бота

```bash
docker compose up -d --build
```

Перевірити логи:

```bash
docker compose logs -f bot
```

Зупинити:

```bash
docker compose down
```

Оновити після змін:

```bash
git pull
docker compose up -d --build
```

## Варіант 2: Render Background Worker

Render зручний тим, що може запускати не вебсайт, а фоновий worker.

1. Залийте проєкт у GitHub.
2. У Render створіть `New` -> `Background Worker`.
3. Оберіть репозиторій.
4. Runtime можна обрати `Docker`.
5. Додайте environment variable:

```env
TELEGRAM_BOT_TOKEN=123456:your-token-here
```

6. Deploy.

У репозиторії вже є `render.yaml`, тому Render також може підхопити конфіг автоматично через Blueprint.

## Варіант 3: Railway

1. Залийте проєкт у GitHub.
2. Створіть новий Railway project з цього репозиторію.
3. Railway побачить Dockerfile і збере контейнер.
4. У Variables додайте:

```env
TELEGRAM_BOT_TOKEN=123456:your-token-here
```

5. Запустіть deployment.

## Важливо про Instagram/Facebook

Instagram і Facebook іноді вимагають авторизацію навіть для публічних роликів. Якщо бот у логах пише, що відео недоступне або потрібен login, додайте cookies-файл:

```env
YTDLP_COOKIES_FILE=/app/cookies.txt
```

Для VPS можна покласти `cookies.txt` поруч із проєктом і змонтувати його в контейнер через `docker-compose.yml`, якщо це знадобиться.
