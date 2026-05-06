# rttf_bridge

Локальный мост для Django-приложения: получает список RTTF URL из Django API, асинхронно скачивает страницы RTTF и отправляет HTML обратно на сервер для парсинга.

## Настройка

1. Скопируйте `.env.example` в `.env`.
2. Заполните `RTTF_AGENT_BASE_URL` и `RTTF_AGENT_TOKEN`.
3. При необходимости настройте `RTTF_AGENT_CONCURRENCY`, `RTTF_AGENT_TIMEOUT` и `RTTF_AGENT_LOG_DIR`.

## Запуск

Через терминал:

```bash
uv run python main.py
```

На macOS можно запускать двойным кликом:

```text
Запустить RTTF агент.command
```

Логи пишутся в `logs/rttf-agent.log`.
