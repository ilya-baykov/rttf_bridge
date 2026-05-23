# rttf_bridge

Локальный мост для Django-приложения: получает список RTTF URL из Django API, асинхронно скачивает страницы RTTF и отправляет HTML обратно на сервер для парсинга.

## Настройка

1. Скопируйте `.env.example` в `.env`.
2. Заполните `RTTF_AGENT_BASE_URL` и `RTTF_AGENT_TOKEN`.
3. При необходимости настройте `RTTF_AGENT_CONCURRENCY`, `RTTF_AGENT_TIMEOUT`, `RTTF_AGENT_SUBMIT_MAX_BYTES` и `RTTF_AGENT_LOG_DIR`.

`RTTF_AGENT_SUBMIT_MAX_BYTES` ограничивает размер одного JSON-запроса с HTML-результатами.
По умолчанию агент отправляет результаты батчами до 750000 байт, чтобы не упираться в лимиты nginx на размер тела запроса.

## Запуск

Через терминал:

```bash
uv run python main.py
```

На macOS можно запускать двойным кликом:

```text
Запустить RTTF агент.command
```

На Windows:

```text
Запустить RTTF агент.bat
```

Для рабочего стола создайте shortcut/alias на соответствующий файл запуска в папке проекта. Не переносите сам `.bat`, `.command` или `.sh` отдельно от проекта: файл запуска ищет `main.py` рядом с собой.

Каждый запуск пишет отдельный лог в `logs/rttf-agent-YYYYMMDD-HHMMSS.log`. Последний запуск также дублируется в `logs/latest.log`.
