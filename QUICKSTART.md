# Quick Start Guide - Local Development

Get HUDS Menu Planning System running locally with Docker Compose.

## 📋 Prerequisites

1. **Docker & Docker Compose** installed on your machine
2. **Telegram Bot Token**:
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow instructions
   - Save the token you receive
3. **OpenAI API Key**:
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Save the key securely

## 🚀 Setup Steps

### 1. Configure Environment

```bash
cd /Users/alarion239/Documents/Scripts/HUDS
cp env.example .env
```

Edit `.env` and add your tokens:

```env
# Required: Add your Telegram bot token
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Required: Add your OpenAI API key  
OPENAI_API_KEY=sk-proj-...your-key-here...
OPENAI_MODEL=gpt-4

# Optional: Customize these
POSTGRES_PASSWORD=your_secure_password_here
DJANGO_SECRET_KEY=your_django_secret_key_here
DJANGO_DEBUG=True
TIME_ZONE=America/New_York
```

### 2. Start the Application

```bash
# Build and start all services
docker-compose up --build -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps

# Run database migrations
docker-compose exec web python manage.py migrate

# Create admin user (will prompt for username, email, password)
docker-compose exec web python manage.py createsuperuser

# Set up scheduled tasks
docker-compose exec web python manage.py setup_periodic_tasks
```

### 3. Access Your Application

- **Admin interface**: http://localhost/admin
- **Telegram bot**: Search for your bot on Telegram and send `/start`

### 4. Test the System

#### Test Menu Fetching
```bash
# Fetch today's menus manually
docker-compose exec web python manage.py fetch_daily_menu

# Fetch specific date
docker-compose exec web python manage.py fetch_daily_menu --date 2025-10-01

# Fetch only breakfast
docker-compose exec web python manage.py fetch_daily_menu --meals breakfast
```

#### Test Telegram Bot

1. Find your bot on Telegram
2. Send `/start` to register
3. Send `/help` to see available commands
4. Send `/nextmeal` to generate a meal plan
5. Send `/logmeal I ate pancakes with syrup` to log a meal

## 📱 Telegram Bot Commands

### User Commands
- `/start` - Register and set up profile
- `/nextmeal` - Generate meal plan (auto-detects time)
- `/logmeal <text>` - Log what you ate with AI parsing
- `/preferences` - Set dietary restrictions
- `/goals` - View/set nutritional goals
- `/today` - Get today's meal plans
- `/feedback` - Reply to messages to give feedback
- `/history` - View meal history
- `/help` - Show commands

### Admin Commands
1. **Make yourself admin** in Django admin:
   - Go to http://localhost/admin
   - Navigate to **User profiles**
   - Edit your profile
   - Check **"Is admin"** checkbox
   - Save

2. **Use admin commands**:
   - `/fetch` - Interactive date picker to fetch menus
   - `/stats` - View system statistics

## 🔧 Common Tasks

### View Logs

```bash
# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f telegram-bot
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
docker-compose logs -f web
```

### Access Database

```bash
# PostgreSQL shell
docker-compose exec db psql -U huds_user -d huds_db

# List tables
\dt

# Query dishes
SELECT name, calories, protein FROM menu_dish LIMIT 10;

# Query menus
SELECT date, meal_type FROM menu_dailymenu;

# Exit
\q
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart telegram-bot
docker-compose restart celery-worker
docker-compose restart celery-beat
```

### Manual Task Execution

```bash
# Django shell
docker-compose exec web python manage.py shell

>>> from users.tasks import generate_and_send_meal_plans
>>> generate_and_send_meal_plans('breakfast')

>>> from menu.tasks import fetch_tomorrow_menus
>>> from datetime import date
>>> fetch_tomorrow_menus(target_date=date.today())
```

### Check Periodic Tasks

1. Go to http://localhost/admin
2. Navigate to **Periodic Tasks** (under Django Celery Beat)
3. You should see 4 tasks:
   - Fetch Tomorrow's Menus (11 PM daily)
   - Generate Breakfast Plans (6:30 AM daily)
   - Generate Lunch Plans (10:30 AM daily)
   - Generate Dinner Plans (3:30 PM daily)

## 🛠️ Development Tools

### Add Test Data

```bash
# Django shell
docker-compose exec web python manage.py shell

>>> from django.contrib.auth.models import User
>>> from users.models import UserProfile

# Create test user
>>> user = User.objects.create_user('testuser', 'test@example.com', 'password123')
>>> profile = UserProfile.objects.create(
...     user=user,
...     telegram_chat_id=123456789,
...     telegram_username='testuser'
... )
```

### Database Backup

```bash
docker-compose exec db pg_dump -U huds_user huds_db > backup.sql
```

### Database Restore

```bash
cat backup.sql | docker-compose exec -T db psql -U huds_user huds_db
```

### Stop Everything

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

## 🐛 Troubleshooting

### Services Won't Start

**Check logs:**
```bash
docker-compose logs
```

**Verify ports are free:**
- Port 80 (nginx)
- Port 5432 (postgres)
- Port 6379 (redis)
- Port 8000 (django)

**Check environment variables:**
```bash
cat .env
```

### Database Connection Errors

**Ensure PostgreSQL is healthy:**
```bash
docker-compose ps db
```

**Check health status:**
```bash
docker-compose exec db pg_isready -U huds_user
```

**Wait for initialization:**
The database needs ~10 seconds to initialize on first run.

### Telegram Bot Not Responding

**Verify token:**
```bash
grep TELEGRAM_BOT_TOKEN .env
```

**Check bot service:**
```bash
docker-compose logs telegram-bot
```

**Test token:**
```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Celery Tasks Not Running

**Check worker logs:**
```bash
docker-compose logs celery-worker
```

**Check beat logs:**
```bash
docker-compose logs celery-beat
```

**Verify Redis:**
```bash
docker-compose exec redis redis-cli ping
# Should return: PONG
```

**Check tasks in admin:**
Go to http://localhost/admin → Periodic Tasks

### OpenAI API Errors

- Verify API key in `.env`
- Check OpenAI account billing and quotas at https://platform.openai.com
- Review celery-worker logs for detailed errors

## 📊 How It Works

### Daily Automation
1. **11:00 PM**: Fetches next day's menus
2. **6:30 AM**: Sends breakfast plans
3. **10:30 AM**: Sends lunch plans
4. **3:30 PM**: Sends dinner plans

### Manual Meal Generation (`/nextmeal`)
- **Before 11 AM** → Breakfast
- **11 AM - 3 PM** → Lunch
- **3 PM - 10 PM** → Dinner
- **After 10 PM** → Next day's breakfast

### Meal Logging (`/logmeal`)
- AI parses natural language
- Matches to HUDS dishes
- Tracks nutrition automatically
- Updates meal history

## ⚙️ Customization

### Change Meal Times

Edit `huds_project/settings.py`:
```python
BREAKFAST_TIME = '06:30'  # Auto-send time
LUNCH_TIME = '10:30'
DINNER_TIME = '15:30'
```

### Adjust Feedback Decay

Edit `users/models.py` → `UserFeedback.get_weighted_rating()`:
```python
# Adjust half_life values (in days)
if self.rating == -2:
    half_life = 180  # 6 months for "never again"
elif self.rating == -1:
    half_life = 90   # 3 months for "bad"
# ... etc
```

### Change AI Model

Edit `.env`:
```env
OPENAI_MODEL=gpt-4-turbo  # or gpt-3.5-turbo for lower cost
```

## 🚀 Deploy to Production

When ready for production, see:
- **[RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)** - Deploy to Railway in 15 minutes

## 📚 Next Steps

1. ✅ Test all bot commands
2. ✅ Add test users via `/start`
3. ✅ Fetch some menus with `/fetch`
4. ✅ Generate meal plans with `/nextmeal`
5. ✅ Provide feedback to train the AI
6. ✅ Log meals with `/logmeal`
7. ✅ Review admin interface features

## 📖 Documentation

- **[README.md](README.md)** - Overview and features
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Technical details
- **[RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)** - Production deployment

---

**Happy coding!** If you encounter issues, check logs first: `docker-compose logs -f`
