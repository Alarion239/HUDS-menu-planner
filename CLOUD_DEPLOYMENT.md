# 🌐 Cloud Deployment Guide - HUDS Meal Planning System

## 🚀 Deployment Options

This guide covers deploying the HUDS system to various cloud platforms. Choose based on your needs:

### **Option 1: Railway (Recommended - Easiest) ⭐**
- **Pros**: Native Docker Compose support, automatic HTTPS, easy scaling
- **Cons**: Slightly more expensive than self-managed options

### **Option 2: DigitalOcean App Platform**
- **Pros**: Good Docker Compose support, reasonable pricing
- **Cons**: Less mature than Railway

### **Option 3: Google Cloud Run + Cloud SQL**
- **Pros**: Serverless, cost-effective for low traffic
- **Cons**: More complex setup, separate services

## 📋 Option 1: Railway (Recommended)

### Prerequisites
1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Push your code to GitHub (Railway deploys from Git)

### Step 1: Environment Variables Setup
Create a `.env` file in your project root:

```bash
# Database
POSTGRES_DB=huds_production
POSTGRES_USER=huds_user
POSTGRES_PASSWORD=your_secure_password_here

# Django
DJANGO_SECRET_KEY=your_production_secret_key_here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-app.railway.app

# APIs (Get these from respective services)
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
OPENAI_API_KEY=your_openai_api_key

# Redis (Railway provides this automatically)
REDIS_URL=${{Redis.REDIS_URL}}

# Timezone
TIME_ZONE=America/New_York
```

### Step 2: Railway Configuration

#### 1. Connect GitHub Repository
- Go to Railway dashboard
- Click "New Project" → "Deploy from GitHub"
- Select your HUDS repository

#### 2. Add PostgreSQL Database
- In Railway dashboard: **Add** → **PostgreSQL**
- Railway will provide `DATABASE_URL` automatically

#### 3. Add Redis Database
- In Railway dashboard: **Add** → **Redis**
- Railway will provide `REDIS_URL` automatically

#### 4. Environment Variables
Railway automatically detects and sets:
- `DATABASE_URL` (from PostgreSQL service)
- `REDIS_URL` (from Redis service)

You need to manually add:
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `DJANGO_SECRET_KEY`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (if not using DATABASE_URL)

#### 5. Custom Commands
Railway runs the `web` service command by default. For Celery services, you'll need to modify `docker-compose.yml` or use Railway's custom commands.

### Step 3: Modify docker-compose.yml for Railway

```yaml
version: '3.8'

services:
  web:
    build: .
    command: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:$PORT --workers 3 huds_project.wsgi:application
    environment:
      - DATABASE_URL=${{PostgreSQL.DATABASE_URL}}
      - REDIS_URL=${{Redis.REDIS_URL}}
      # Add other environment variables
    ports:
      - "${{PORT}}:${{PORT}}"

  # Note: Celery services need custom Railway services or background jobs
  # Railway doesn't support multiple processes in one service easily
```

### Step 4: Deploy

1. **Push to GitHub**: `git push origin main`
2. **Railway Auto-Deploy**: Railway automatically redeploys when you push
3. **Manual Deploy**: Click "Deploy" in Railway dashboard

### Step 5: Post-Deployment Setup

#### 1. Run Migrations
```bash
# In Railway shell or via CLI
python manage.py migrate
```

#### 2. Create Superuser
```bash
python manage.py createsuperuser
```

#### 3. Set up Periodic Tasks
- Access Django admin at `https://your-app.railway.app/admin`
- Go to **Periodic Tasks** (Django Celery Beat)
- Add the tasks from QUICKSTART.md

### Step 6: Domain & SSL
Railway provides:
- ✅ Automatic HTTPS
- ✅ Custom domains (add via dashboard)
- ✅ SSL certificates

---

## 📋 Option 2: DigitalOcean App Platform

### Prerequisites
1. **DigitalOcean Account**: Sign up at [digitalocean.com](https://digitalocean.com)
2. **GitHub Repository**: Push your code to GitHub

### Step 1: Environment Setup
Similar to Railway, create `.env` with production values.

### Step 2: DigitalOcean Configuration

#### 1. Create App
- Go to **Apps** → **Create App**
- Choose **GitHub** as source
- Select your repository

#### 2. Add Database
- **Add Database** → **PostgreSQL**
- DigitalOcean provides connection details

#### 3. Environment Variables
Add all required environment variables in the App Platform dashboard.

#### 4. Deploy
DigitalOcean handles the deployment automatically.

---

## 📋 Option 3: Google Cloud Run (Advanced)

### Prerequisites
1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured

### Step 1: Set up Services

#### 1. Cloud SQL (PostgreSQL)
```bash
gcloud sql instances create huds-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud sql databases create huds_production --instance=huds-db
gcloud sql users create huds_user --instance=huds-db --password=your_password
```

#### 2. Cloud Redis
```bash
gcloud redis instances create huds-redis \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_6_x
```

#### 3. Cloud Run (Web Service)
```bash
gcloud run deploy huds-web \
  --source=. \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${DATABASE_URL},REDIS_URL=${REDIS_URL},DJANGO_SECRET_KEY=${SECRET_KEY}"
```

### Step 4: Environment Variables
Set all required environment variables in Cloud Run configuration.

---

## 🔧 Production Considerations

### **Environment Variables Security**
- **Never commit** `.env` files to Git
- Use **GitHub Secrets** or cloud platform secret management
- Generate strong, unique secrets for production

### **Database Backups**
```bash
# PostgreSQL backup (run weekly)
pg_dump -h your-db-host -U huds_user huds_production > backup_$(date +%Y%m%d).sql
```

### **Monitoring & Logging**
- **Railway**: Built-in monitoring dashboard
- **DigitalOcean**: App Platform metrics
- **Google Cloud**: Cloud Monitoring

### **Scaling**
- **Railway**: Automatic scaling based on usage
- **DigitalOcean**: Manual scaling in App Platform
- **Google Cloud**: Auto-scaling policies

### **Cost Optimization**
- **Start small**: Use smallest instances initially
- **Monitor usage**: Scale based on actual traffic
- **Auto-scaling**: Enable where available

---

## 🚨 Important Production Notes

### **API Keys & Tokens**
- **Telegram Bot Token**: Keep secret, never log it
- **OpenAI API Key**: Monitor usage for costs
- **Database Passwords**: Use strong, unique passwords

### **Security Headers**
Add to Django settings for production:
```python
SECURE_HSTS_SECONDS = 31536000
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### **Static Files**
```python
# In settings.py
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### **Error Monitoring**
Add Sentry or similar for production error tracking.

---

## 🎯 Quick Start Commands

### **Railway Deployment**
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Link project
railway link

# 4. Add services
railway add postgresql
railway add redis

# 5. Set environment variables
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set OPENAI_API_KEY=your_key

# 6. Deploy
railway up
```

### **Domain Setup (Railway)**
- Go to Railway dashboard → **Settings** → **Domains**
- Add your custom domain
- Railway provides SSL automatically

---

## 📊 Cost Estimates (Monthly)

### **Railway** (Hobby Plan)
- **Web Service**: $5
- **PostgreSQL**: $10
- **Redis**: $10
- **Total**: ~$25/month

### **DigitalOcean App Platform**
- **App**: $12 (1GB RAM)
- **Database**: $15 (PostgreSQL)
- **Total**: ~$27/month

### **Google Cloud Run**
- **Cloud Run**: $0-10 (pay per use)
- **Cloud SQL**: $10-20
- **Cloud Redis**: $5-10
- **Total**: $15-40/month

**Railway is recommended for ease of deployment and management!** 🚂
