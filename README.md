# Flask Site Crawler

Microservice Flask pour crawler un site web, stocker les URLs dans PostgreSQL et exposer des métriques.


## Installation

### 1. Cloner le projet
```bash
git clone https://github.com/LaMonaLisa34/Micro_Service_Flask_Site_Crawler.git
cd Micro_Service_Flask_Site_Crawler
```

### 2. Lancer avec Docker Compose
```bash
docker-compose up -d --build
```

### 3. Exemple docker-compose.yml
```yaml
services:
  crawler:
    build: .
    ports:
      - "5000:5000"
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: crawlerdb
    ports:
      - "5432:5432"
```

---

## Utilisation

### Lancer un crawl :
```bash
curl -X POST "http://localhost:5000/crawl_site?url=https://chevauxdumonde.com"
```

### Lister les URLs :
```bash
curl http://localhost:5000/urls
```

### Rapport global :
```bash
curl http://localhost:5000/report
```

### Exemple de sortie :
```json
{
  "total_urls": 317,
  "active_urls": 315,
  "inactive_urls": 2,
  "avg_response_time": 0.201,
  "error_rate": "0.63%"
}
```

---

## Monitoring avec Prometheus et Grafana

### Exemple `prometheus.yml`
```yaml
scrape_configs:
  - job_name: "crawler"
    static_configs:
      - targets: ["crawler:5000"]
```

---

## Stack

- Flask + aiohttp  
- SQLAlchemy + PostgreSQL  
- Prometheus + Grafana  
