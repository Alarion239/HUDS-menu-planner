# Quick Start Guide

## Prerequisites

1. **Get a Telegram Bot Token**:
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow the instructions
   - Save the token you receive

2. **Get an OpenAI API Key**:
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Save the key securely

## Setup Steps

Choose your deployment method:

### 🚀 Option A: Local Development (Quick Start)

#### 1. Configure Environment

Create a `.env` file in the HUDS directory:

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

# Optional: Customize these
POSTGRES_PASSWORD=your_secure_password_here
DJANGO_SECRET_KEY=your_django_secret_key_here
```

### 2. Start the Application

```bash
# Build and start all services
docker-compose up --build -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps

# Run database migrations
docker-compose exec web python manage.py migrate

# Create admin user
docker-compose exec web python manage.py createsuperuser
```

### 3. Set Up Scheduled Tasks

Access Django admin to configure Celery Beat schedules:

1. Go to http://localhost/admin
2. Login with your superuser credentials
3. Navigate to "Periodic tasks" under "Django Celery Beat"
4. Add the following tasks:

**Task 1: Fetch Tomorrow's Menus**
- Name: `Fetch Tomorrow's Menus`
- Task: `menu.tasks.fetch_tomorrow_menus`
- Schedule: Crontab - `0 23 * * *` (11:00 PM daily)
- Enabled: ✓

**Task 2: Breakfast Plans**
- Name: `Generate and Send Breakfast Plans`
- Task: `users.tasks.generate_and_send_meal_plans`
- Arguments: `["breakfast"]`
- Schedule: Crontab - `30 6 * * *` (6:30 AM daily)
- Enabled: ✓

**Task 3: Lunch Plans**
- Name: `Generate and Send Lunch Plans`
- Task: `users.tasks.generate_and_send_meal_plans`
- Arguments: `["lunch"]`
- Schedule: Crontab - `30 10 * * *` (10:30 AM daily)
- Enabled: ✓

**Task 4: Dinner Plans**
- Name: `Generate and Send Dinner Plans`
- Task: `users.tasks.generate_and_send_meal_plans`
- Arguments: `["dinner"]`
- Schedule: Crontab - `30 15 * * *` (3:30 PM daily)
- Enabled: ✓

### 4. Test the System

#### Test Menu Fetching

```bash
# Fetch today's menus manually
docker-compose exec web python manage.py fetch_daily_menu

# Fetch specific date
docker-compose exec web python manage.py fetch_daily_menu --date 2025-09-30

# Fetch only breakfast
docker-compose exec web python manage.py fetch_daily_menu --meals breakfast
```

#### Test Telegram Bot

1. Find your bot on Telegram (search for the bot name you created)
2. Send `/start` to register
3. Send `/help` to see available commands
4. Send `/preferences vegetarian, no pork` to set dietary restrictions

#### View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f telegram-bot
docker-compose logs -f celery-worker
docker-compose logs -f web
```

## Common Tasks

### Add a New User via Admin

1. Go to http://localhost/admin
2. Click "Users" → "Add user"
3. Create username and password
4. Click "User profiles" → "Add user profile"
5. Select the user
6. Add Telegram chat ID (user can get this by messaging your bot)
7. Set nutritional goals and preferences
8. Enable notifications

### Manually Generate Meal Plan

```bash
# Via Django shell
docker-compose exec web python manage.py shell

>>> from users.tasks import generate_meal_plans_for_meal
>>> generate_meal_plans_for_meal('breakfast')
```

### Check Database

```bash
# Access PostgreSQL
docker-compose exec db psql -U huds_user -d huds_db

# List tables
\dt

# Query dishes
SELECT name, calories, protein FROM menu_dish LIMIT 10;

# Query menus
SELECT date, meal_type, COUNT(*) FROM menu_dailymenu_dishes GROUP BY date, meal_type;

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

### Stop Everything

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

### ☁️ Option B: Cloud Deployment (Production)

For production deployment, see **[CLOUD_DEPLOYMENT.md](../CLOUD_DEPLOYMENT.md)** for detailed instructions.

**Railway is the recommended option** for its ease of deployment and excellent Docker Compose support.

**Quick Railway Deployment:**
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and link project
railway login
railway link

# 3. Add services
railway add postgresql
railway add redis

# 4. Set secrets
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set OPENAI_API_KEY=your_key

# 5. Deploy
railway up
```

## Troubleshooting

### Bot Not Responding

```bash
# Check bot logs
docker-compose logs telegram-bot

# Restart bot
docker-compose restart telegram-bot

# Verify token in .env
grep TELEGRAM_BOT_TOKEN .env
```

### Database Connection Issues

```bash
# Check database status
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Celery Tasks Not Running

```bash
# Check celery worker logs
docker-compose logs celery-worker

# Check celery beat logs
docker-compose logs celery-beat

# Restart celery services
docker-compose restart celery-worker celery-beat
```

### OpenAI API Errors

- Verify API key in `.env`
- Check OpenAI account billing and quotas
- Review celery-worker logs for detailed errors

## Next Steps

1. **Customize Meal Times**: Edit `BREAKFAST_TIME`, `LUNCH_TIME`, `DINNER_TIME` in `huds_project/settings.py`

2. **Adjust Nutritional Goals**: Update default values in `users/models.py` → `UserProfile`

3. **Modify Feedback Decay**: Change half-life values in `users/models.py` → `UserFeedback.get_weighted_rating()`

4. **Add More Bot Commands**: Extend `bot/handlers.py` with additional functionality

5. **Customize AI Prompts**: Modify prompt templates in `huds_lib/model.py`

## Support

- Check logs: `docker-compose logs -f`
- Access admin: http://localhost/admin
- Review README.md for detailed documentation
