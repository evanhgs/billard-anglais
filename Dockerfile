FROM python:3.13-alpine

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

EXPOSE 8000

# PORT est fourni par l'hébergeur (ex. Render) ; 8000 par défaut.
# Un seul worker : les salles de jeu sont gardées en mémoire.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8000} --worker-class eventlet --workers 1 app:app"]
