#!/bin/zsh
cd "$(dirname "$0")"

echo "Запуск RTTF агента..."
echo "Лог пишется в: $(pwd)/logs/rttf-agent.log"
echo

uv run python main.py
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "Готово."
else
  echo "Завершено с ошибкой. Код: $status"
fi

echo
echo "Окно можно закрыть."
read -r "?Нажмите Enter для выхода..."
