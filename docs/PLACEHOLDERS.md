# EduAgent Placeholders and Dummy Values Guide

This document lists all placeholder values, dummy data, and configuration items that need to be replaced with actual values for production deployment.

## 1. Environment Variables (`.env` file)

### Critical - Must Replace Before Running

| Variable | Location | Current Value | Replacement | How to Get |
|----------|----------|----------------|-------------|-----------|
| `GEMINI_API_KEY` | `.env` | `your-gemini-api-key-here` | Your actual API key | https://ai.google.dev (free tier available) |
| `JWT_SECRET_KEY` | `.env` | `change-me-in-production` | Random 32+ char string | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `NEXTAUTH_SECRET` | `.env` | `change-me-in-production` | Random 32+ char string | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

### Database Credentials (Change for Production)

| Variable | Location | Current Value | Recommendation |
|----------|----------|----------------|-----------------|
| `POSTGRES_USER` | `.env` | `eduagent` | Keep for dev, change for production |
| `POSTGRES_PASSWORD` | `.env` | `eduagent_dev` | **MUST CHANGE** for production |
| `POSTGRES_DB` | `.env` | `eduagent` | Keep or change as needed |

### URLs (Update for Your Domain)

| Variable | Location | Current Value | Production Value |
|----------|----------|----------------|-----------------|
| `NEXT_PUBLIC_API_URL` | `.env` | `http://localhost:8000` | `https://api.yourdomain.com` |
| `NEXTAUTH_URL` | `.env` | `http://localhost:3000` | `https://yourdomain.com` |

---

## 2. Demo User Account

### Location
- **File**: `backend/scripts/seed_demo.py`
- **Lines**: 45-60 (approx)

### Current Dummy Data
```python
demo_user = User(
    email="demo@eduagent.com",
    full_name="Demo Student",
    hashed_password=hash_password("demo123"),
    role="student"
)
```

### How to Replace
1. **For Development**: Keep as-is for testing
2. **For Production**: 
   - Remove or disable the seed script
   - Create admin user via API: `POST /api/auth/register`
   - Delete demo account from database:
     ```sql
     DELETE FROM users WHERE email = 'demo@eduagent.com';
     ```

---

## 3. Demo Subjects and Concepts

### Location
- **File**: `backend/scripts/seed_demo.py`
- **Lines**: 65-150 (approx)

### Current Dummy Data
```python
subjects = [
    Subject(name="Machine Learning", code="ML", description="..."),
    Subject(name="Human-Computer Interaction", code="HCI", description="..."),
    Subject(name="Cybersecurity", code="CS", description="..."),
    Subject(name="Multisensor Algorithms", code="MSA", description="..."),
]
```

### How to Replace
1. **For Development**: Keep as-is for testing
2. **For Production**:
   - Upload your actual course materials via `/admin/upload`
   - Create subjects via `/admin/subjects`
   - Create concepts via `/admin/concepts/[subjectId]`
   - Disable seed script in `docker-compose.prod.yml`

---

## 4. Default Configuration Values

### Location
- **File**: `backend/app/config.py`
- **Lines**: 1-39

### Current Dummy/Default Values

| Setting | Current Value | Recommendation | How to Change |
|---------|---------------|-----------------|---------------|
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Adjust based on security needs | Edit `config.py` line 22 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Adjust based on security needs | Edit `config.py` line 23 |
| `QDRANT_HOST` | `localhost` | Change to `qdrant` in Docker | Edit `config.py` line 13 |
| `REDIS_URL` | `redis://localhost:6379/0` | Change to `redis://redis:6379/0` in Docker | Edit `config.py` line 17 |

### For Production
```python
# backend/app/config.py

class Settings(BaseSettings):
    # Change these for production
    JWT_SECRET_KEY: str = "your-secure-random-key"  # Generate new key
    NEXTAUTH_SECRET: str = "your-secure-random-key"  # Generate new key
    
    # Database (use managed service like AWS RDS)
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@prod-db.example.com:5432/eduagent"
    
    # Qdrant (use managed service or self-hosted)
    QDRANT_HOST: str = "qdrant.example.com"
    QDRANT_PORT: int = 6333
    
    # Redis (use managed service like AWS ElastiCache)
    REDIS_URL: str = "redis://prod-redis.example.com:6379/0"
    
    # LLM (ensure API key is valid)
    GEMINI_API_KEY: str = "your-actual-gemini-key"
```

---

## 5. Frontend Configuration

### Location
- **File**: `frontend/src/lib/api.ts`
- **Lines**: 1-20

### Current Dummy Values
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
```

### How to Replace
1. Set `NEXT_PUBLIC_API_URL` in `.env` to your backend URL
2. For production: `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`

---

## 6. NextAuth Configuration

### Location
- **File**: `frontend/src/app/api/auth/[...nextauth]/route.ts`
- **Lines**: 1-50 (approx)

### Current Dummy Values
```typescript
providers: [
  CredentialsProvider({
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "Password", type: "password" }
    },
    async authorize(credentials) {
      // Calls backend API at NEXT_PUBLIC_API_URL
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
        method: 'POST',
        body: JSON.stringify(credentials),
      });
      // ...
    }
  })
],
secret: process.env.NEXTAUTH_SECRET,
```

### How to Replace
- `NEXTAUTH_SECRET` must be set in `.env` (generate new for production)
- `NEXTAUTH_URL` must match your frontend domain

---

## 7. Database Seed Data

### Location
- **File**: `backend/scripts/seed_demo.py`

### Current Dummy Data Includes
- 4 demo subjects (ML, HCI, Cybersecurity, MSA)
- 60+ demo concepts with prerequisites
- 1 demo user (demo@eduagent.com / demo123)
- Sample concept mastery scores (0.0 - 1.0)
- Sample conversations

### How to Replace
1. **Keep for Development**: Useful for testing
2. **Remove for Production**:
   ```bash
   # Don't run the seed profile
   docker compose -f docker-compose.prod.yml up -d
   # (omit --profile seed)
   ```
3. **Add Real Data**:
   - Upload PDFs via `/admin/upload`
   - Create subjects via `/admin/subjects`
   - Create concepts via `/admin/concepts`
   - Create users via `/register`

---

## 8. Docker Compose Configuration

### Location
- **File**: `docker-compose.yml` (dev) and `docker-compose.prod.yml` (prod)

### Current Dummy/Default Values

#### Development (`docker-compose.yml`)
```yaml
services:
  postgres:
    environment:
      POSTGRES_USER: ${POSTGRES_USER}  # eduagent
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # eduagent_dev
      POSTGRES_DB: ${POSTGRES_DB}  # eduagent
```

#### Production (`docker-compose.prod.yml`)
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G  # Adjust based on your server
  
  frontend:
    deploy:
      resources:
        limits:
          memory: 512M  # Adjust based on your server
```

### How to Replace
1. **Database**: Use managed service (AWS RDS, Google Cloud SQL)
2. **Qdrant**: Use managed service or self-hosted instance
3. **Redis**: Use managed service (AWS ElastiCache, Redis Cloud)
4. **Memory limits**: Adjust based on your server capacity

---

## 9. LLM Provider (Gemini)

### Location
- **File**: `.env`
- **Backend Usage**: `backend/app/agents/` (all agent files)

### Current Configuration
```bash
GEMINI_API_KEY=your-gemini-api-key-here
```

### How to Replace
1. **Get API Key**:
   - Go to https://ai.google.dev
   - Click "Get API Key"
   - Create new project or use existing
   - Copy API key
2. **Set in `.env`**:
   ```bash
   GEMINI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
   ```
3. **Verify**:
   ```bash
   docker exec eduagent-backend python -c "from app.config import get_settings; print('✅ API key loaded')"
   ```

### Alternative LLM Providers
To use OpenAI, Anthropic, or other providers instead:
1. Update `backend/app/agents/base.py` to use different LLM client
2. Update all agent files to use new LLM
3. Update `.env` with new API key
4. Update `pyproject.toml` dependencies

---

## 10. Email Configuration (Optional)

### Location
- **File**: Not yet implemented (placeholder for future)

### Current Status
- Email notifications are **NOT** implemented
- To add email support:
  1. Install: `pip install python-multipart python-dotenv sendgrid`
  2. Add to `.env`:
     ```bash
     SENDGRID_API_KEY=your-sendgrid-key
     ADMIN_EMAIL=admin@yourdomain.com
     ```
  3. Create email service in `backend/app/services/email.py`
  4. Add email routes in `backend/app/routers/`

---

## 11. Logging Configuration

### Location
- **File**: `backend/app/main.py`
- **Lines**: 50-80 (approx)

### Current Configuration
```python
# Structured logging via structlog
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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

### How to Replace
- **For Development**: Keep as-is (JSON logs to stdout)
- **For Production**: 
  - Add log aggregation (ELK, Datadog, CloudWatch)
  - Update `structlog` configuration to send logs to service
  - Add log retention policy

---

## 12. Monitoring and Analytics (Optional)

### Location
- **File**: Not yet implemented (placeholder for future)

### Current Status
- Basic agent logging is implemented (`agent_logs` table)
- To add monitoring:
  1. Install: `pip install prometheus-client`
  2. Add Prometheus metrics to `backend/app/main.py`
  3. Deploy Prometheus + Grafana
  4. Create dashboards for:
     - Agent response times
     - API latency
     - Database query times
     - Cache hit rates

---

## 13. Security Checklist for Production

### Before Deploying to Production

- [ ] Change `JWT_SECRET_KEY` (generate new)
- [ ] Change `NEXTAUTH_SECRET` (generate new)
- [ ] Change `POSTGRES_PASSWORD` (strong password)
- [ ] Set `GEMINI_API_KEY` (valid key)
- [ ] Update `NEXT_PUBLIC_API_URL` (production domain)
- [ ] Update `NEXTAUTH_URL` (production domain)
- [ ] Disable seed script in `docker-compose.prod.yml`
- [ ] Delete demo user from database
- [ ] Enable HTTPS (use Let's Encrypt or AWS ACM)
- [ ] Set up firewall rules
- [ ] Enable database backups
- [ ] Set up monitoring and alerting
- [ ] Review and update CORS settings
- [ ] Set up rate limiting
- [ ] Enable audit logging

---

## 14. Summary Table

| Item | Type | Current Value | Production Value | Priority |
|------|------|---------------|------------------|----------|
| Gemini API Key | Secret | `your-gemini-api-key-here` | Real key | **CRITICAL** |
| JWT Secret | Secret | `change-me-in-production` | Random 32+ chars | **CRITICAL** |
| NextAuth Secret | Secret | `change-me-in-production` | Random 32+ chars | **CRITICAL** |
| DB Password | Secret | `eduagent_dev` | Strong password | **CRITICAL** |
| API URL | Config | `http://localhost:8000` | `https://api.yourdomain.com` | **HIGH** |
| Frontend URL | Config | `http://localhost:3000` | `https://yourdomain.com` | **HIGH** |
| Demo User | Data | `demo@eduagent.com` | Delete or disable | **MEDIUM** |
| Demo Subjects | Data | 4 demo subjects | Real course data | **MEDIUM** |
| Memory Limits | Config | 2GB backend, 512MB frontend | Adjust to server | **LOW** |
| Logging | Config | JSON to stdout | Log aggregation | **LOW** |

---

## 15. Quick Reference Commands

### Generate Secure Secrets
```bash
# Generate JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate NEXTAUTH_SECRET
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate strong DB password
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

### Verify Configuration
```bash
# Check Gemini API key
docker exec eduagent-backend python -c "from app.config import get_settings; s = get_settings(); print(f'Key: {s.GEMINI_API_KEY[:20]}...')"

# Check database connection
docker exec eduagent-postgres psql -U eduagent -d eduagent -c "SELECT 1"

# Check Redis connection
docker exec eduagent-redis redis-cli ping

# Check Qdrant connection
curl http://localhost:6333/health
```

### Update Environment Variables
```bash
# Edit .env
nano .env

# Restart services to apply changes
docker compose down
docker compose up -d
```

---

**Last Updated**: July 17, 2026  
**Version**: 1.0  
**Status**: Complete
