#!/bin/zsh
# Запуск панели: останавливает старый экземпляр на том же порту и стартует заново.
cd "$(dirname "$0")"
PORT="${PORT:-5050}"
OLD=$(lsof -tnP -iTCP:$PORT -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLD" ]; then
    if ps -o command= -p $OLD | grep -q "app.py"; then
        echo "Останавливаю старый сервер (PID $OLD)..."
        kill $OLD; sleep 1
    else
        echo "Порт $PORT занят другой программой: $(ps -o command= -p $OLD)"
        echo "Запустите на другом порту: PORT=5060 ./run.sh"
        exit 1
    fi
fi
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
echo "Панель: http://127.0.0.1:$PORT"
exec .venv/bin/python -W ignore::Warning app.py
