# EduAgent Configuration Guide

Complete guide to configuring EduAgent for development and production.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Database Configuration](#database-configuration)
3. [LLM Configuration](#llm-configuration)
4. [Authentication](#authentication)
5. [Frontend Configuration](#frontend-configuration)
6. [Backend Configuration](#backend-configuration)
7. [Docker Configuration](#docker-configuration)
8. [Production Deployment](#production-deployment)

---

## Environment Setup

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Edit `.env` File

Open `.env` in your editor and configure the following sections:

#### Database Configuration
```bash
# PostgreSQL credentials
POSTGRES_USER=eduagent
POSTGRES_PASSWORD=eduagent_dev  # Change for production
POSTGRES_DB=eduagent
DATABASE_URL=postgresql+asyncpg://eduagent:eduagent_dev@postgres:5432/eduagent
```

#### Vector Database (Qdrant)
```bash
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

#### Cache (Redis)
```bash
REDIS_URL=redis://redis:6379/0
```

#### LLM (Gemini)
```bash
# Get API key from https://ai.google.dev
GEMINI_API_KEY=your-actual-gemini-api-key
```

#### Authentication
```bash
# Generate new secrets for production
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# NextAuth configuration
NEXTAUTH_SECRET=change-me-in-production
NEXTAUTH_URL=http://localhost:3000
```

#### Frontend API
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Database Configuration

### PostgreSQL Setup

#### Development (Docker)
```bash
# PostgreSQL runs in Docker automatically
# Connection: localhost:5432
# User: eduagent
# Password: eduagent_dev
# Database: eduagent
```

#### Production (AWS RDS)
```bash
# 1. Create RDS instance
# 2. Update DATABASE_URL in .env
DATABASE_URL=postgresql+asyncpg://user:password@prod-db.rds.amazonaws.com:5432/eduagent

# 3. Run migrations
docker exec eduagent-backend alembic upgrade head
```

### Database Migrations

#### View Migration Status
```bash
docker exec eduagent-backend alembic current
```

#### Run Migrations
```bash
docker exec eduagent-backend alembic upgrade head
```

#### Rollback Last Migration
```bash
docker exec eduagent-backend alembic downgrade -1
```

#### Create New Migration
```bash
docker exec eduagent-backend alembic revision --autogenerate -m "description"
```

#### View Migration History
```bash
docker exec eduagent-backend alembic history
```

### Database Backup and Restore

#### Backup Database
```bash
# Backup to file
docker exec eduagent-postgres pg_dump -U eduagent eduagent > backup.sql

# Backup with compression
docker exec eduagent-postgres pg_dump -U eduagent -Fc eduagent > backup.dump
```

#### Restore Database
```bash
# Restore from SQL file
docker exec -i eduagent-postgres psql -U eduagent eduagent < backup.sql

# Restore from compressed dump
docker exec -i eduagent-postgres pg_restore -U eduagent -d eduagent backup.dump
```

#### Access PostgreSQL Directly
```bash
docker exec -it eduagent-postgres psql -U eduagent -d eduagent

# Useful queries
\dt                    # List tables
\d table_name          # Describe table
SELECT COUNT(*) FROM users;  # Count records
```

---

## LLM Configuration

### Gemini API Setup

#### 1. Get API Key
- Go to https://ai.google.dev
- Click "Get API Key"
- Create new project or use existing
- Copy API key

#### 2. Set in `.env`
```bash
GEMINI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
```

#### 3. Verify Configuration
```bash
# Check if API key is loaded
docker exec eduagent-backend python -c "from app.config import get_settings; s = get_settings(); print(f'✅ API key loaded: {s.GEMINI_API_KEY[:20]}...')"

# Test API call
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents": [{"parts": [{"text": "Hello"}]}]}'
```

### Using Alternative LLM Providers

#### OpenAI (GPT-4)
```bash
# 1. Install OpenAI client
pip install openai

# 2. Update .env
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# 3. Update backend/app/agents/base.py
from openai import OpenAI
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 4. Update all agent files to use OpenAI client
```

#### Anthropic (Claude)
```bash
# 1. Install Anthropic client
pip install anthropic

# 2. Update .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# 3. Update backend/app/agents/base.py
from anthropic import Anthropic
client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
```

#### Local LLM (Ollama)
```bash
# 1. Install Ollama from https://ollama.ai
# 2. Run local model
ollama run mistral

# 3. Update .env
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434

# 4. Update backend/app/agents/base.py to use local endpoint
```

---

## Authentication

### JWT Configuration

#### Generate Secure Secrets
```bash
# Generate JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: example_output_here

# Generate NEXTAUTH_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: example_output_here
```

#### Update `.env`
```bash
JWT_SECRET_KEY=your-generated-secret-here
NEXTAUTH_SECRET=your-generated-secret-here
```

### User Roles

#### Available Roles
- `student` — Can use all learning features
- `admin` — Can manage subjects, concepts, custom agents, view analytics

#### Create Admin User
```bash
# Via API
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password",
    "full_name": "Admin User"
  }'

# Then update role in database
docker exec -it eduagent-postgres psql -U eduagent -d eduagent
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

### Session Configuration

#### Adjust Token Expiration
Edit `.env`:
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30    # Access token validity
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7       # Refresh token validity
```

#### Adjust in Code
Edit `backend/app/config.py`:
```python
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Change here
JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # Change here
```

---

## Frontend Configuration

### Environment Variables

#### Development
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-here
```

#### Production
```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXTAUTH_URL=https://yourdomain.com
NEXTAUTH_SECRET=your-production-secret-here
```

### Theme Configuration

#### Dark Mode
- Automatically enabled/disabled based on system preference
- User can toggle in sidebar
- Preference saved to localStorage

#### Customize Colors
Edit `frontend/tailwind.config.ts`:
```typescript
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: '#your-color',
        secondary: '#your-color',
      }
    }
  }
}
```

### Build Configuration

#### Development Build
```bash
npm run dev
```

#### Production Build
```bash
npm run build
npm start
```

#### Build Output
- `.next/` — Compiled Next.js application
- `public/` — Static assets

---

## Backend Configuration

### FastAPI Configuration

#### Server Settings
Edit `backend/app/main.py`:
```python
app = FastAPI(
    title="EduAgent API",
    description="Multi-Agent AI Educational Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)
```

#### CORS Settings
Edit `backend/app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Database Connection Pool

Edit `backend/app/config.py`:
```python
# Adjust connection pool size
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,        # Number of connections to keep open
    max_overflow=20,     # Additional connections when pool is full
    pool_pre_ping=True,  # Test connections before using
)
```

### Logging Configuration

Edit `backend/app/main.py`:
```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()  # JSON logs
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### Cache Configuration

#### Redis Cache Settings
Edit `backend/app/config.py`:
```python
REDIS_URL: str = "redis://redis:6379/0"
```

#### Cache TTL
Edit `backend/app/services/cache.py`:
```python
CACHE_TTL = 300  # 5 minutes in seconds
```

---

## Docker Configuration

### Development Docker Compose

Edit `docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

### Production Docker Compose

Edit `docker-compose.prod.yml`:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G      # Adjust based on server
          cpus: '2'       # Adjust based on server
```

### .dockerignore Files

#### Backend `.dockerignore`
- Excludes: `venv/`, `tests/`, `__pycache__/`, `.git/`, etc.
- Reduces image size by ~50%

#### Frontend `.dockerignore`
- Excludes: `node_modules/`, `.next/`, `.git/`, etc.
- Reduces image size by ~60%

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Generate new `JWT_SECRET_KEY`
- [ ] Generate new `NEXTAUTH_SECRET`
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Set valid `GEMINI_API_KEY`
- [ ] Update `NEXT_PUBLIC_API_URL` to production domain
- [ ] Update `NEXTAUTH_URL` to production domain
- [ ] Disable seed script in `docker-compose.prod.yml`
- [ ] Delete demo user from database
- [ ] Enable HTTPS/SSL
- [ ] Set up database backups
- [ ] Set up monitoring and alerting
- [ ] Review security settings

### Deploy to AWS

#### 1. Create RDS Database
```bash
# Create PostgreSQL RDS instance
# Update DATABASE_URL in .env
```

#### 2. Create ElastiCache Redis
```bash
# Create Redis cluster
# Update REDIS_URL in .env
```

#### 3. Create Qdrant Instance
```bash
# Option 1: Self-hosted on EC2
# Option 2: Use Qdrant Cloud (https://cloud.qdrant.io)
# Update QDRANT_HOST in .env
```

#### 4. Deploy to ECS/Fargate
```bash
# Push images to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag eduagent-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/eduagent-backend:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/eduagent-backend:latest

# Create ECS task definition and service
# Configure load balancer and auto-scaling
```

### Deploy to Google Cloud

#### 1. Create Cloud SQL Database
```bash
gcloud sql instances create eduagent-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=us-central1
```

#### 2. Create Cloud Memorystore Redis
```bash
gcloud redis instances create eduagent-redis \
  --size=1 \
  --region=us-central1
```

#### 3. Deploy to Cloud Run
```bash
# Build and push images
gcloud builds submit --tag gcr.io/PROJECT_ID/eduagent-backend

# Deploy backend
gcloud run deploy eduagent-backend \
  --image gcr.io/PROJECT_ID/eduagent-backend \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=your-key
```

### Deploy to DigitalOcean

#### 1. Create Droplet
```bash
# Create Ubuntu 22.04 droplet
# Install Docker and Docker Compose
```

#### 2. Clone Repository
```bash
git clone https://github.com/abhyuditagrawal/Capstone-AgenticAI-Educational.git
cd Capstone-AgenticAI-Educational
```

#### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with production values
```

#### 4. Start Services
```bash
docker compose -f docker-compose.prod.yml up -d
```

#### 5. Set Up Reverse Proxy (Nginx)
```bash
# Install Nginx
sudo apt-get install nginx

# Configure reverse proxy
sudo nano /etc/nginx/sites-available/default
```

### SSL/HTTPS Configuration

#### Using Let's Encrypt
```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --nginx -d yourdomain.com

# Auto-renew
sudo systemctl enable certbot.timer
```

#### Update Nginx Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

**Last Updated**: July 17, 2026  
**Version**: 1.0  
**Status**: Complete
