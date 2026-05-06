#!/bin/sh
cd "$(dirname "$0")" || exit 1

echo "Запуск RTTF агента..."
echo "Лог пишется в: $(pwd)/logs/rttf-agent.log"
echo

if ! command -v uv >/dev/null 2>&1; then
  echo "Не найден uv в PATH."
  echo "Установите uv или запускайте из окружения, где команда uv доступна."
  exit 1
fi

uv run python main.py
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "Готово."
else
  echo "Завершено с ошибкой. Код: $status"
fi

exit "$status"
