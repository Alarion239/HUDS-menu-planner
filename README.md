# HUDS Menu Planning System

A Django application that fetches daily menus from Harvard University Dining Services (HUDS), generates personalized meal plans using AI, and delivers recommendations via Telegram bot.

## ✨ Features

- **Automated Menu Fetching**: Nightly scraping of HUDS website for nutritional data
- **AI-Powered Meal Planning**: OpenAI GPT generates balanced, personalized meal recommendations  
- **Telegram Bot Interface**: Interactive bot for meal plans, feedback, and meal logging
- **Smart Meal Detection**: `/nextmeal` auto-detects which meal to generate based on time
- **Meal Logging**: `/logmeal` lets you log what you actually ate with free-form text
- **User Preferences**: Tracks dietary restrictions, nutritional goals, and food feedback
- **Time-Weighted Feedback**: Rating system that learns preferences over time
- **Admin Controls**: Interactive date picker for manual menu fetching and system stats

## 🚀 Quick Start

### Option 1: Railway Deployment (Recommended)

**Deploy to Railway in 15 minutes** - See **[RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)**

Railway advantages:
- ✅ Easy multi-service deployment (Web, Worker, Scheduler, Bot)
- ✅ Managed PostgreSQL and Redis databases
- ✅ Automatic deploys from GitHub
- ✅ Free $5 trial + affordable pricing ($5/month hobby plan)
- ✅ Built-in monitoring and logging

### Option 2: Local Development

See **[QUICKSTART.md](QUICKSTART.md)** for Docker Compose setup.

## 📱 Telegram Bot Commands

### User Commands
- `/start` - Register and set up your profile
- `/nextmeal` - Generate meal plan (auto-detects breakfast/lunch/dinner based on time)
- `/logmeal <description>` - Log what you actually ate with AI parsing
- `/preferences` - Update dietary restrictions
- `/goals` - Set nutritional goals  
- `/today` - Get today's meal plans
- `/feedback` - Reply to any message to provide feedback on dishes
- `/history` - View your meal history
- `/help` - Show available commands

### Admin Commands
- `/fetch` - Interactive date picker to manually fetch menus
- `/stats` - View system statistics

## 🤖 How It Works

### Daily Automation
1. **11:00 PM**: Fetches next day's menus with full nutrition data
2. **6:30 AM**: Generates and sends personalized breakfast plans
3. **10:30 AM**: Generates and sends personalized lunch plans
4. **3:30 PM**: Generates and sends personalized dinner plans

### Manual Meal Generation (`/nextmeal`)
Time-based auto-detection:
- **Before 11 AM** → Breakfast
- **11 AM - 3 PM** → Lunch
- **3 PM - 10 PM** → Dinner
- **After 10 PM** → Next day's breakfast

### Meal Logging (`/logmeal`)
Log what you actually ate using natural language:
- `/logmeal I had a chicken breast and side salad`
- `/logmeal Half a waffle with strawberries and yogurt`
- AI extracts dishes, quantities, and calculates nutrition
- Tracks meal history for better future recommendations

### Feedback System
- Reply to meal plans or dishes with feedback
- AI extracts ratings (-2 to +2 scale)
- Time-weighted: Recent feedback has more influence
- Automatically improves future recommendations

## 🏗️ Architecture

### Services
1. **App Service**: Django web app + admin interface
2. **Worker Service**: Celery background task processor
3. **Cron Service**: Celery Beat scheduler for periodic tasks
4. **Bot Service**: Telegram bot for user interactions
5. **Database**: PostgreSQL for persistent storage
6. **Redis**: Message broker for Celery tasks

### Key Apps
- **menu**: Manages dishes and daily menus
- **users**: User profiles, meal plans, history, feedback
- **bot**: Telegram bot handlers and commands
- **huds_lib**: HUDS scraping and AI meal planning logic

## 📊 Database Models

- **Dish**: Stores dish info and 14+ nutritional fields
- **DailyMenu**: Links dishes to specific dates and meals
- **UserProfile**: User settings, goals, Telegram integration
- **MealPlan**: AI-generated plans with status tracking
- **MealHistory**: Records of actually consumed meals
- **UserFeedback**: Time-weighted ratings and comments

## 🛠️ Development

### Local Setup
```bash
# Clone and configure
cd /path/to/HUDS
cp env.example .env
# Edit .env with your tokens

# Start services
docker-compose up --build

# Initialize
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### Management Commands
```bash
# Fetch menus
docker-compose exec web python manage.py fetch_daily_menu --date 2025-10-01

# Set up periodic tasks
docker-compose exec web python manage.py setup_periodic_tasks

# Create superuser (Railway auto-runs this)
docker-compose exec web python manage.py create_default_superuser
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f telegram-bot
docker-compose logs -f celery-worker
```

## 🔐 Environment Variables

### Required
```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token

# OpenAI API Key
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4

# Django Secret Key (generate with: python -c "import secrets; print(secrets.token_urlsafe(50))")
DJANGO_SECRET_KEY=your_secret_key
```

### Railway Specific
```env
# Auto-configured by Railway services
PGDATABASE=${{Postgres.PGDATABASE}}
PGUSER=${{Postgres.PGUSER}}
PGPASSWORD=${{Postgres.PGPASSWORD}}
PGHOST=${{Postgres.PGHOST}}
PGPORT=${{Postgres.PGPORT}}
REDIS_URL=${{Redis.REDIS_URL}}

# Production settings
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=*.railway.app,*.up.railway.app
```

## 📈 Customization

### Meal Times
Edit in `huds_project/settings.py`:
```python
BREAKFAST_TIME = '06:30'  # Auto-generated plan send time
LUNCH_TIME = '10:30'
DINNER_TIME = '15:30'
```

### Feedback Decay Rates
Modify in `users/models.py` → `UserFeedback.get_weighted_rating()`:
```python
# Adjust half_life values (in days)
rating == -2: half_life = 180  # Never again
rating == -1: half_life = 90   # Bad
rating == 0:  half_life = 30   # Neutral
rating == 1:  half_life = 60   # Good
rating == 2:  half_life = 90   # Love it
```

## 🐛 Troubleshooting

### Celery Tasks Not Running
- Check Worker logs: `docker-compose logs celery-worker`
- Check Scheduler logs: `docker-compose logs celery-beat`  
- Verify periodic tasks in Django admin
- Ensure Redis is running

### Bot Not Responding
- Verify `TELEGRAM_BOT_TOKEN` in environment
- Check Bot Service logs
- Test token: `curl https://api.telegram.org/bot<TOKEN>/getMe`

### Database Connection Issues
- Ensure PostgreSQL is running
- Check database credentials
- Wait for health checks to pass

## 📚 Documentation

- **[RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)** - Deploy to Railway in 15 minutes
- **[QUICKSTART.md](QUICKSTART.md)** - Local Docker Compose setup
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Technical overview and architecture

## 🎓 Recent Updates

- ✅ Fixed Celery Beat meal notification bug  
- ✅ Added interactive date picker for `/fetch` command
- ✅ Added `/logmeal` for logging actual meals with AI parsing
- ✅ Improved nutrition data extraction (fixed carbohydrate parsing)
- ✅ Time-based meal detection for `/nextmeal` command
- ✅ Added admin commands (`/fetch`, `/stats`)

## 📝 License

This project is for educational purposes.

## 🙏 Credits

- HUDS Menu Scraping: Based on `HUDS_MVP` parser
- AI Meal Planning: OpenAI GPT integration
- Telegram Bot: python-telegram-bot library
