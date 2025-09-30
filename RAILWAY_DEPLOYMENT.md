# Railway Deployment Guide for HUDS Menu Planning System

This guide explains how to deploy the HUDS Menu Planning System to [Railway](https://railway.app) using their "majestic monolith" architecture.

## 📋 Overview

Railway deployment splits your Docker Compose services into separate Railway services:
- **App Service**: Django web application (Gunicorn)
- **Worker Service**: Celery background task processor
- **Cron Service**: Celery Beat scheduler
- **Bot Service**: Telegram bot
- **Database**: PostgreSQL (managed by Railway)
- **Redis**: Redis cache (managed by Railway)

## 🚀 Quick Start

### Prerequisites
1. A Railway account ([sign up](https://railway.app))
2. Your code pushed to a GitHub repository
3. Required API keys:
   - Telegram Bot Token (from [@BotFather](https://t.me/botfather))
   - OpenAI API Key

### Step-by-Step Deployment

#### 1. Create a New Railway Project

1. Go to [Railway](https://railway.app) and click **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway to access your GitHub account
4. Select your HUDS repository

#### 2. Add PostgreSQL Database

1. In your Railway project canvas, click **Create** or right-click
2. Select **Database** → **Add PostgreSQL**
3. Railway will automatically provision and deploy a PostgreSQL instance
4. Note: Railway automatically creates environment variables like `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`

#### 3. Add Redis Database

1. Click **Create** again
2. Select **Database** → **Add Redis**
3. Railway will provision Redis and create `REDIS_URL` variable

#### 4. Configure App Service (Web)

1. Rename the auto-created service to **"App Service"** (or create a new **Empty Service**)
2. Go to **Settings** tab:
   
   **Source Section:**
   - Connect to your GitHub repository
   - Set **Root Directory**: Leave blank (or `/` if needed)
   
   **Deploy Section:**
   - **Build Command**: Leave empty (auto-detected)
   - **Start Command**: `sh -c "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:$PORT --workers 3 huds_project.wsgi:application"`
   
3. Go to **Variables** tab and add:

```env
# Reference Railway's PostgreSQL service
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}

# Reference Railway's Redis service
REDIS_URL=${{Redis.REDIS_URL}}

# Django settings
DJANGO_SECRET_KEY=<generate-a-strong-random-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=*.railway.app,*.up.railway.app

# API Keys
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-4

# Time Zone
TIME_ZONE=America/New_York
```

> **Note**: Use the syntax `${{ServiceName.VARIABLE}}` to reference variables from other services. Learn more about [Railway variable references](https://docs.railway.app/guides/variables#reference-variables).

4. Click **Deploy**

#### 5. Configure Worker Service (Celery)

1. Click **Create** → **Empty Service**
2. Name it **"Worker Service"**
3. Go to **Settings**:
   
   **Source Section:**
   - Connect to the same GitHub repository
   
   **Deploy Section:**
   - **Start Command**: `celery -A huds_project worker --loglevel=info --concurrency=3`
   
4. Go to **Variables** tab and add **the same environment variables** as App Service:

```env
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}
REDIS_URL=${{Redis.REDIS_URL}}
DJANGO_SECRET_KEY=<same-as-app-service>
DJANGO_DEBUG=False
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_MODEL=gpt-4
TIME_ZONE=America/New_York
```

5. Click **Deploy**

> **Concurrency Note**: `--concurrency=3` means the worker can process up to 3 tasks in parallel. Adjust based on your Railway plan's resources.

#### 6. Configure Cron Service (Celery Beat)

1. Click **Create** → **Empty Service**
2. Name it **"Cron Service"**
3. Go to **Settings**:
   
   **Source Section:**
   - Connect to the same GitHub repository
   
   **Deploy Section:**
   - **Start Command**: `celery -A huds_project beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler`
   
4. Go to **Variables** tab and add **the same environment variables** as above

5. Click **Deploy**

#### 7. Configure Bot Service (Telegram Bot)

1. Click **Create** → **Empty Service**
2. Name it **"Bot Service"**
3. Go to **Settings**:
   
   **Source Section:**
   - Connect to the same GitHub repository
   
   **Deploy Section:**
   - **Start Command**: `Capython manage.py run_telegram_bot`
   
4. Go to **Variables** tab and add **the same environment variables** as above

5. Click **Deploy**

#### 8. Set Up Public Domain (App Service Only)

1. Go to your **App Service**
2. Click on the **Settings** tab
3. Scroll to **Networking** section
4. Click **Generate Domain**
5. Railway will create a public URL like `https://your-app.up.railway.app`

> **Important**: Only the App Service needs a public domain. The Worker, Cron, and Bot services run in the background.

#### 9. Initialize the Database

After all services are deployed:

1. Go to **App Service** → **View Logs** to verify migrations ran successfully
2. Create a superuser by running a one-off command:
   - In the App Service, go to **Settings** → **Service** → scroll to bottom
   - Look for "Run a command" or use Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run command in App Service context
railway run python manage.py createsuperuser
```

#### 10. Configure Scheduled Tasks

1. Access your Django admin at `https://your-app.up.railway.app/admin`
2. Log in with your superuser credentials
3. Navigate to **Django Celery Beat** → **Periodic Tasks**
4. Add the following tasks:

| Task Name | Task | Cron Schedule | Arguments | Description |
|-----------|------|---------------|-----------|-------------|
| Fetch Tomorrow's Menus | `menu.tasks.fetch_tomorrow_menus` | `0 23 * * *` | `[]` | Runs at 11 PM daily |
| Breakfast Plans | `users.tasks.generate_and_send_meal_plans` | `30 6 * * *` | `["breakfast"]` | Runs at 6:30 AM |
| Lunch Plans | `users.tasks.generate_and_send_meal_plans` | `30 10 * * *` | `["lunch"]` | Runs at 10:30 AM |
| Dinner Plans | `users.tasks.generate_and_send_meal_plans` | `30 15 * * *` | `["dinner"]` | Runs at 3:30 PM |

## 🔒 Security Best Practices

### Generate a Strong Django Secret Key

```python
# Run this in Python to generate a secure key
import secrets
print(secrets.token_urlsafe(50))
```

### Production Settings Checklist

- ✅ `DJANGO_DEBUG=False` in production
- ✅ `DJANGO_SECRET_KEY` is random and secret
- ✅ `DJANGO_ALLOWED_HOSTS` includes your Railway domain
- ✅ Keep API keys secure and never commit them to git
- ✅ Use Railway's environment variables, not `.env` files

## 📊 Monitoring Your Deployment

### View Logs

Each service has its own logs:
1. Click on a service
2. Go to **Deployments** tab
3. Click **View Logs**

### Check Service Health

- **App Service**: Visit your public URL, should show Django admin
- **Worker Service**: Logs should show "celery@... ready"
- **Cron Service**: Logs should show "beat: Starting..."
- **Bot Service**: Send `/start` to your bot on Telegram

### Database Monitoring

- Go to **Postgres** service → **Metrics** to see database usage
- Use Railway's query tab to run SQL queries

## 🐛 Troubleshooting

### Service Won't Start

**Check build logs:**
- Verify all dependencies in `requirements.txt` are installing
- Ensure Python version compatibility

**Check environment variables:**
- Make sure all required variables are set
- Verify syntax: `${{Postgres.PGDATABASE}}` not `${Postgres.PGDATABASE}`

### Database Connection Issues

**Error**: "could not connect to server"
- Ensure database service is deployed and healthy
- Check that `PGHOST`, `PGPORT` variables are correctly referenced
- Verify network connectivity between services

### Static Files Not Loading

**Issue**: CSS/JS not appearing on admin site
- Ensure `collectstatic` ran in the start command
- Check WhiteNoise is in `MIDDLEWARE` (after SecurityMiddleware)
- Verify `STATICFILES_STORAGE` is set correctly

### Celery Tasks Not Running

**Worker not processing tasks:**
- Check Worker Service logs for errors
- Verify `REDIS_URL` is correctly set
- Ensure Redis service is running

**Beat not scheduling:**
- Check Cron Service logs
- Verify periodic tasks are configured in Django admin
- Ensure `DatabaseScheduler` is being used

### Telegram Bot Not Responding

**Bot offline:**
- Check Bot Service logs for errors
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Test token with Telegram API: `curl https://api.telegram.org/bot<TOKEN>/getMe`

## 💰 Cost Optimization

Railway offers:
- **Free Trial**: $5 credit to test deployment
- **Hobby Plan**: $5/month (500 hours of execution time)
- **Pro Plan**: $20/month (more resources)

### Tips to Reduce Costs:
1. **Optimize concurrency**: Lower `--concurrency` values use less memory
2. **Scale down when not needed**: Use Railway's sleep feature for dev environments
3. **Monitor usage**: Check Railway dashboard for resource consumption
4. **Combine services**: For smaller loads, you might combine worker + cron into one service

## 🔄 Deploying Updates

Railway automatically redeploys when you push to your GitHub repository:

1. Make changes to your code
2. Commit and push to GitHub
3. Railway detects the change and redeploys affected services

### Manual Redeployment:

1. Go to a service
2. Click **Deploy** button (top right)
3. Select **Latest commit** or a specific commit

## 📚 Additional Resources

- [Railway Django Guide](https://docs.railway.app/guides/django)
- [Railway Environment Variables](https://docs.railway.app/guides/variables)
- [Railway CLI Documentation](https://docs.railway.app/develop/cli)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html)

## ✅ Deployment Checklist

Before going live, ensure:

- [ ] All 6 services deployed successfully
- [ ] Public domain generated for App Service
- [ ] Superuser created
- [ ] Periodic tasks configured in Django admin
- [ ] Telegram bot responds to `/start`
- [ ] Test menu fetching: Run `fetch_daily_menu` task manually
- [ ] Test meal plan generation for a user
- [ ] All environment variables are set correctly
- [ ] `DEBUG=False` in production
- [ ] Logs show no errors

## 🎉 Success!

Once everything is deployed, your HUDS Menu Planning System is live! Users can:
1. Start the Telegram bot with `/start`
2. Set preferences with `/preferences`
3. Receive personalized meal plans at configured times
4. Provide feedback to improve recommendations

---

**Need Help?** 
- Railway Discord: [railway.app/discord](https://railway.app/discord)
- Railway Docs: [docs.railway.app](https://docs.railway.app)
- File issues on your GitHub repository
