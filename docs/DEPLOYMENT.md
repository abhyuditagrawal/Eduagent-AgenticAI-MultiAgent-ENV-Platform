# Deployment Guide

## Prerequisites
- Docker & Docker Compose v2+
- Google Gemini API key (free: https://aistudio.google.com/apikey)

---

## Option 1: Docker Compose (Recommended)

### Quick Start
```bash
# Clone the repository
git clone https://github.com/abhyuditagrawal/Capstone-AgenticAI-Educational.git
cd Capstone-AgenticAI-Educational

# Copy env file and fill in your Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY, JWT_SECRET_KEY, NEXTAUTH_SECRET

# Start all services (development)
docker-compose up --build

# Start all services (production)
docker-compose -f docker-compose.prod.yml up --build -d

# Seed demo data (optional)
docker-compose -f docker-compose.prod.yml run seed
```

### Services
| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Next.js app |
| Backend | 8000 | FastAPI + agents |
| PostgreSQL | 5432 | Database |
| Qdrant | 6333 | Vector DB |

### Environment Variables
See `.env.example` for all required variables.

**Important for production:**
- Set `JWT_SECRET_KEY` to a random 32+ character string
- Set `NEXTAUTH_SECRET` to a random 32+ character string
- Set `GEMINI_API_KEY` to your Google Gemini API key

---

## Option 2: Railway

1. Fork this repository on GitHub
2. Go to [Railway](https://railway.app) and create a new project
3. Add services:
   - **PostgreSQL** (from Railway template)
   - **Backend** (from GitHub repo, set root to `backend/`)
   - **Frontend** (from GitHub repo, set root to `frontend/`)
4. Add **Qdrant** as a Docker service (image: `qdrant/qdrant:latest`)
5. Set environment variables in Railway dashboard (same as `.env.example`)
6. Update `DATABASE_URL` to use Railway's PostgreSQL connection string
7. Update `QDRANT_HOST` to Railway's Qdrant service hostname
8. Deploy

---

## Option 3: Self-Hosted VPS

```bash
# On your VPS (Ubuntu 22.04+)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin

# Clone and setup
git clone https://github.com/abhyuditagrawal/Capstone-AgenticAI-Educational.git
cd Capstone-AgenticAI-Educational
cp .env.example .env
nano .env  # Edit environment variables

# Production deployment
docker compose -f docker-compose.prod.yml up --build -d

# Check status
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### Reverse Proxy (Nginx)
For HTTPS, add Nginx in front:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Database Backup & Restore

### Backup
```bash
docker exec eduagent-postgres pg_dump -U eduagent eduagent > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
docker exec -i eduagent-postgres psql -U eduagent eduagent < backup_20250115.sql
```

---

## Development Setup (Without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[test]"

# Start PostgreSQL and Qdrant locally (or via Docker)
docker run -d --name pg -p 5432:5432 -e POSTGRES_USER=eduagent -e POSTGRES_PASSWORD=eduagent_dev -e POSTGRES_DB=eduagent postgres:16
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# Run backend
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
# Backend
cd backend && pytest --cov=app

# Frontend
cd frontend && npx vitest run
```
