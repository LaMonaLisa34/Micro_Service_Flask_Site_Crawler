FROM python:3.11-slim

# Installer dépendances système (pour psycopg2)
RUN apt-get update && apt-get install -y gcc libpq-dev

WORKDIR /app

# Installer dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier ton code
COPY . .

# Lancer Flask
CMD ["flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5051"]
