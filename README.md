# whichbeer

Веб-приложение для подбора пива: пользователь выбирает напиток, который хочет попробовать, и несколько напитков для сравнения (по вкусу которые ему нравятся) — приложение считает вероятность того, что новый напиток понравится, на основе параметров (ABV/IBU) и смысловой близости описаний.

## Технологии

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) — HTTP API
- [PostgreSQL](https://www.postgresql.org/) (`psycopg2`) — хранение каталога напитков и предпосчитанных эмбеддингов
- [pandas](https://pandas.pydata.org/) / [NumPy](https://numpy.org/) — векторные вычисления сходства
- [curl_cffi](https://github.com/yifeikong/curl_cffi) — обход TLS-фингерпринтинга Cloudflare при обращении к Untappd
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — парсинг HTML-страниц Untappd
- [uv](https://docs.astral.sh/uv/) — управление зависимостями и запуск

**Frontend**
- Ванильные HTML/CSS/JS, без фреймворков и сборки — один файл `frontend/index.html`
- Конфигурация адреса API во время выполнения через `frontend/config.js` (подставляется CI при деплое)

**ML / данные**
- [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) (`sentence-transformers`) — эмбеддинги описаний напитков для смыслового сравнения. Считаются **офлайн** отдельным скриптом и хранятся в Postgres — сама модель не грузится в проде на каждый запрос, чтобы не превышать лимиты памяти хостинга.
- Поиск напитков — публичный Algolia-индекс Untappd (тот же, что использует сам сайт untappd.com)

**Инфраструктура**
- Frontend деплоится на **GitHub Pages** через GitHub Actions (`.github/workflows/deploy.yml`)
- Backend деплоится на **Railway** (`Procfile`)
- База данных — управляемый Postgres на Railway

## Структура проекта

```
app/
  data/
    postgres.py                    # доступ к Postgres: CRUD по таблице beer + эмбеддинги
    scrape_untappd_descriptions.py # поиск и скрейпинг описаний с Untappd
    compute_embeddings.py          # офлайн-скрипт: считает эмбеддинги описаний и пишет в БД
    migrate.py, data.py            # старые скрипты (SQLite) — легаси
  main/
    main.py                        # FastAPI-приложение и роуты /api/*
    system.py                      # расчёт итоговой вероятности (ABV/IBU + эмбеддинги)
    descriptions_matching.py       # косинусное сходство по эмбеддингам из БД
frontend/
  index.html                       # весь UI (разметка + стили + JS)
  config.js                        # window.API_BASE — адрес backend, задаётся при деплое
  assets/foam.png                  # текстура пены для анимации вероятности
.github/workflows/deploy.yml       # деплой frontend на GitHub Pages
Procfile                           # команда запуска backend на Railway
```

## API

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/search_beers?beer_name=...` | Поиск напитков (через Algolia-индекс Untappd) |
| GET | `/api/beer_description?beer_name=...` | Описание напитка из локальной базы |
| POST | `/api/add_beer` | Добавить напиток в базу, если его там ещё нет |
| POST | `/api/probability` | Вероятность понравится: `{beer_name, comparisons: [...]}` → `{probability}` |

## Локальный запуск

```bash
uv sync

# backend (нужен DATABASE_URL в окружении)
DATABASE_URL=postgresql://... uv run uvicorn app.main.main:app --reload

# frontend — просто статика, например:
python -m http.server 4173 --directory frontend
```

Перед первым запуском база должна быть заполнена (`postgres.pd_to_sql()`) и эмбеддинги посчитаны:

```bash
DATABASE_URL=postgresql://... uv run python -m app.data.compute_embeddings
```

## Деплой

- **Backend (Railway)**: команда запуска — `Procfile` (`uv run uvicorn app.main.main:app --host 0.0.0.0 --port $PORT`). Требуется переменная `DATABASE_URL`.
- **Frontend (GitHub Pages)**: пуш в `main` триггерит `deploy.yml`, который подставляет реальный адрес backend в `config.js` из переменной репозитория `API_URL` (Settings → Secrets and variables → Actions → Variables).
