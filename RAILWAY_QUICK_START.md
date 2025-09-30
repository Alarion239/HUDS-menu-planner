# Railway Quick Start Guide

A streamlined guide to deploy HUDS Menu Planning System to Railway in under 15 minutes.

## 🚀 Prerequisites

- [ ] GitHub repository with your HUDS code
- [ ] [Railway account](https://railway.app) (free to start)
- [ ] Telegram Bot Token from [@BotFather](https://t.me/botfather)
- [ ] OpenAI API Key

## 📦 One-Time Setup (Do Once)

### 1. Create Railway Project

```bash
# Visit https://railway.app
# Click "New Project" → "Deploy from GitHub repo"
# Select your HUDS repository
```

### 2. Add Databases (Click "Create" for each)

- Add **PostgreSQL** database
- Add **Redis** database

### 3. Create Services

Create 4 separate services by clicking **Create** → **Empty Service** for each:

| Service Name | Start Command | Public Domain? |
|--------------|---------------|----------------|
| **App Service** | `sh -c "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:$PORT --workers 3 huds_project.wsgi:application"` | ✅ Yes |
| **Worker Service** | `celery -A huds_project worker --loglevel=info --concurrency=3` | ❌ No |
| **Cron Service** | `celery -A huds_project beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler` | ❌ No |
| **Bot Service** | `python manage.py run_telegram_bot` | ❌ No |

For each service:
1. Go to **Settings** → **Source** → Connect your GitHub repo
2. Go to **Settings** → **Deploy** → Add the start command from table above
3. Continue to environment variables below

## 🔧 Environment Variables (Add to ALL Services)

Click **Variables** tab in each service and add:

```env
# Database (auto-filled by Railway)
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}

# Redis (auto-filled by Railway)
REDIS_URL=${{Redis.REDIS_URL}}

# Django Settings
DJANGO_SECRET_KEY=<generate-random-50-char-string>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=*.railway.app,*.up.railway.app

# API Keys (your actual keys)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4

# Optional
TIME_ZONE=America/New_York
```

### Generate Django Secret Key

```python
# Run in Python shell
import secrets
print(secrets.token_urlsafe(50))
```

## 🌐 Generate Public Domain (App Service Only)

1. Go to **App Service**
2. Click **Settings** → **Networking**
3. Click **Generate Domain**
4. Save the URL (e.g., `https://huds-production.up.railway.app`)

## 🎬 Deploy All Services

Click **Deploy** button on each service in this order:
1. Postgres & Redis (should already be running)
2. App Service
3. Worker Service
4. Cron Service
5. Bot Service

## 👤 Create Superuser

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and link to project
railway login
railway link

# Create superuser
railway run python manage.py createsuperuser
```

Or use Railway dashboard's run command feature.

## ⏰ Configure Scheduled Tasks

1. Visit `https://your-app.up.railway.app/admin`
2. Login with superuser credentials
3. Go to **Periodic Tasks** (under Django Celery Beat)
4. Add these 4 tasks:

**Fetch Menus (11 PM Daily)**
```
Name: Fetch Tomorrow's Menus
Task: menu.tasks.fetch_tomorrow_menus
Cron: 0 23 * * *
Arguments: []
```

**Breakfast Plans (6:30 AM Daily)**
```
Name: Breakfast Plans
Task: users.tasks.generate_and_send_meal_plans
Cron: 30 6 * * *
Arguments: ["breakfast"]
```

**Lunch Plans (10:30 AM Daily)**
```
Name: Lunch Plans
Task: users.tasks.generate_and_send_meal_plans
Cron: 30 10 * * *
Arguments: ["lunch"]
```

**Dinner Plans (3:30 PM Daily)**
```
Name: Dinner Plans
Task: users.tasks.generate_and_send_meal_plans
Cron: 30 15 * * *
Arguments: ["dinner"]
```

## ✅ Test Your Deployment

### 1. Check Service Health

```bash
railway logs --service "App Service"
railway logs --service "Worker Service"
railway logs --service "Cron Service"
railway logs --service "Bot Service"
```

Or view logs in Railway dashboard.

### 2. Test Telegram Bot

Open Telegram and send `/start` to your bot. You should get a welcome message.

### 3. Manually Fetch Menu

In Django admin, go to **Periodic Tasks** → Find "Fetch Tomorrow's Menus" → Click "Run task"

Check Worker Service logs to see task execution.

## 🎉 You're Live!

Your HUDS system is now deployed! Users can:
- `/start` - Register
- `/preferences vegetarian, no nuts` - Set preferences
- `/goals` - View nutrition goals
- Receive meal plans automatically

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Service won't start | Check logs for errors; verify all env variables are set |
| Database connection failed | Ensure Postgres service is running; check variable syntax `${{Postgres.PGDATABASE}}` |
| Static files missing | Verify `collectstatic` in start command; check WhiteNoise in settings |
| Bot not responding | Check bot token; view Bot Service logs |
| Tasks not running | Check Cron Service logs; verify periodic tasks in admin |

## 📊 Monitor Costs

- View usage in Railway dashboard
- Free trial: $5 credit
- Hobby plan: $5/month
- Pro plan: $20/month for more resources

## 🔄 Update Deployment

Just push to GitHub! Railway auto-deploys on push.

```bash
git add .
git commit -m "Update feature"
git push origin main
# Railway automatically redeploys
```

## 📚 Full Documentation

For detailed explanations, see [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)

---

**Need help?** Join [Railway Discord](https://railway.app/discord)
