# Railway Quick Start Guide

Deploy HUDS Menu Planning System to Railway in under 15 minutes.

## 🚀 Prerequisites

- [ ] GitHub repository with your HUDS code
- [ ] [Railway account](https://railway.app) (free to start)
- [ ] Telegram Bot Token from [@BotFather](https://t.me/botfather)
- [ ] OpenAI API Key from [platform.openai.com](https://platform.openai.com/api-keys)

## 📦 Step-by-Step Deployment

### 1. Create Railway Project

1. Visit [railway.app](https://railway.app)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your HUDS repository
4. Railway will create an initial service - **rename it to "App Service"**

### 2. Add Databases

Click **Create** for each:
- **PostgreSQL** database
- **Redis** database

Railway auto-creates environment variables for these.

### 3. Create Additional Services

Create 3 more **Empty Services** (Click **Create** → **Empty Service**):

| Service Name | Start Command |
|--------------|---------------|
| **Worker Service** | `celery -A huds_project worker --loglevel=info --concurrency=3` |
| **Cron Service** | `celery -A huds_project beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler` |
| **Bot Service** | `python manage.py run_telegram_bot` |

For each service:
1. Go to **Settings** → **Source** → Connect your GitHub repo
2. Go to **Settings** → **Deploy** → Add the start command from table above

### 4. Configure App Service

Go to **App Service** → **Settings** → **Deploy**:

**Start Command:**
```bash
sh -c "python manage.py migrate && python manage.py collectstatic --noinput && python manage.py create_default_superuser && python manage.py setup_periodic_tasks && gunicorn --bind 0.0.0.0:$PORT --workers 3 huds_project.wsgi:application"
```

This command:
- Runs database migrations
- Collects static files
- Creates default superuser (`admin`/`admin123`)
- Sets up periodic tasks automatically
- Starts the web server

### 5. Environment Variables (Add to ALL Services)

Click **Variables** tab in each service and add:

```env
# Database (auto-filled by referencing Postgres service)
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}

# Redis (auto-filled by referencing Redis service)
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

**Generate Django Secret Key:**
```python
# Run in Python shell
import secrets
print(secrets.token_urlsafe(50))
```

**Important Notes:**
- Use the syntax `${{ServiceName.VARIABLE}}` to reference other services
- Add these variables to **ALL 4 services** (App, Worker, Cron, Bot)
- No quotes around the `${{...}}` references

### 6. Generate Public Domain (App Service Only)

1. Go to **App Service** → **Settings** → **Networking**
2. Click **Generate Domain**
3. Save the URL (e.g., `https://huds-production.up.railway.app`)

### 7. Deploy All Services

Click **Deploy** button on each service in this order:
1. Postgres & Redis (should already be running)
2. **App Service** (wait for it to complete)
3. Worker Service
4. Cron Service
5. Bot Service

### 8. Access Your Application

1. Visit `https://your-app.up.railway.app/admin`
2. Login with default credentials:
   - **Username**: `admin`
   - **Password**: `admin123`
3. **Change the password immediately!**

### 9. Make Yourself a Bot Admin

1. In Django admin, go to **User profiles**
2. Find your profile (or create one by using `/start` on Telegram first)
3. Check the **"Is admin"** checkbox
4. Click **Save**
5. Now you can use `/fetch` and `/stats` commands on Telegram!

## ✅ Test Your Deployment

### 1. Check Service Health

View logs for each service in Railway dashboard:
- **App Service**: Should show "Starting gunicorn"
- **Worker Service**: Should show "celery@... ready"
- **Cron Service**: Should show "beat: Starting..."
- **Bot Service**: Should show "Bot is running!"

### 2. Test Telegram Bot

1. Open Telegram and find your bot
2. Send `/start` - should get welcome message
3. Send `/help` - should see command list
4. Send `/nextmeal` - should generate a meal plan (if menus are fetched)

### 3. Verify Scheduled Tasks

1. In Django admin, go to **Periodic Tasks** (under Django Celery Beat)
2. You should see 4 tasks already configured:
   - Fetch Tomorrow's Menus (11 PM daily)
   - Breakfast Plans (6:30 AM daily)
   - Lunch Plans (10:30 AM daily)
   - Dinner Plans (3:30 PM daily)

### 4. Manually Fetch Menu

1. On Telegram, use `/fetch` command (admin only)
2. Click a date from the interactive picker
3. Wait for confirmation message with stats

## 🎉 You're Live!

Your bot is now deployed! Users can:
- `/start` - Register
- `/nextmeal` - Get meal plan (auto-detects time)
- `/logmeal I ate chicken and salad` - Log actual meals
- `/preferences vegetarian, no nuts` - Set preferences
- `/feedback` - Reply to any meal plan to give feedback
- Receive automated meal plans at 6:30 AM, 10:30 AM, and 3:30 PM

## 🐛 Common Issues

| Problem | Solution |
|---------|----------|
| Service won't start | Check logs; verify all env variables are set correctly |
| Database connection failed | Ensure Postgres is running; check syntax `${{Postgres.PGDATABASE}}` (no quotes!) |
| Static files missing | Verify `collectstatic` in App Service start command |
| Bot not responding | Check TELEGRAM_BOT_TOKEN; view Bot Service logs |
| Tasks not running | Check Cron Service logs; verify periodic tasks exist in admin |
| Admin password doesn't work | Check App Service logs for "Superuser created/updated" message |

## 🔧 Update Deployment

Railway auto-deploys when you push to GitHub:

```bash
git add .
git commit -m "Update feature"
git push origin main
# Railway automatically redeploys
```

## 💰 Cost Estimate

- **Free Trial**: $5 credit (enough for testing)
- **Hobby Plan**: $5/month (500 hours execution time)
- **Pro Plan**: $20/month (more resources)

**Typical usage**: 4 services running 24/7 ≈ $5-10/month

## 📊 Monitor Usage

- View resource usage in Railway dashboard
- Check service metrics for CPU/memory
- Monitor database storage

## 🔒 Security Best Practices

1. **Change default admin password** immediately after first login
2. Use **strong, unique** Django secret key (50+ characters)
3. Keep `DJANGO_DEBUG=False` in production
4. Never commit API keys to GitHub
5. Use Railway's environment variables, not `.env` files

## 📚 Next Steps

1. **Customize meal times**: Edit in Django admin or `settings.py`
2. **Add more users**: Have them send `/start` to the bot
3. **Set up feedback**: Reply to meal plans to train the AI
4. **Monitor logs**: Check Railway dashboard regularly
5. **Update the app**: Just push to GitHub!

## 🆘 Need Help?

- **Railway Discord**: [railway.app/discord](https://railway.app/discord)
- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Check logs**: View in Railway dashboard for each service
- **Review README**: See [README.md](README.md) for detailed info

---

**Deployment complete!** Your HUDS Menu Planning System is now live on Railway. 🎊
