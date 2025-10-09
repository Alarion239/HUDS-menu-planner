# HUDS Menu Planning System - Project Summary

## ✅ Project Status: Production Ready

A fully functional Django application deployed on Railway with PostgreSQL, Redis, Celery scheduling, and Telegram bot interface for personalized HUDS menu planning.

## 📁 Project Structure

```
HUDS/
├── huds_project/              # Django project
│   ├── settings.py            # Configuration (Railway + Docker compatible)
│   ├── celery.py              # Celery configuration
│   ├── urls.py                # URL routing
│   └── wsgi.py                # WSGI application
│
├── huds_lib/                  # HUDS scraping library
│   ├── webpage.py             # URL generation
│   ├── parser.py              # Menu parsing & nutrition fetching
│   └── model.py               # AI meal planning logic
│
├── menu/                      # Menu management app
│   ├── models.py              # Dish & DailyMenu models
│   ├── admin.py               # Admin interface
│   ├── tasks.py               # Celery tasks (fetch menus)
│   └── management/commands/
│       ├── fetch_daily_menu.py       # CLI: Fetch menus
│       └── setup_periodic_tasks.py   # CLI: Auto-setup Celery Beat tasks
│
├── users/                     # User management app
│   ├── models.py              # UserProfile, MealPlan, MealHistory, UserFeedback
│   ├── admin.py               # Admin interface
│   ├── tasks.py               # Celery tasks (generate & send plans)
│   └── management/commands/
│       └── create_default_superuser.py  # CLI: Auto-create admin user
│
├── bot/                       # Telegram bot app
│   ├── handlers.py            # Bot command handlers
│   └── management/commands/
│       └── run_telegram_bot.py  # Bot runner
│
├── docker-compose.yml         # Local development orchestration
├── Dockerfile                 # Container definition
├── Procfile                   # Railway process definitions
├── requirements.txt           # Python dependencies
└── env.example                # Environment variables template
```

## 🎯 Core Features

### 1. Automated Menu Fetching ✅
- **Nightly task**: Fetches next day's breakfast, lunch, dinner at 11 PM
- **Nutritional data**: Complete nutrition facts for all dishes
- **Database storage**: Efficient PostgreSQL schema with proper indexing
- **Admin control**: `/fetch` command with interactive date picker

### 2. AI-Powered Meal Planning ✅
- **OpenAI Integration**: Uses GPT-4 for intelligent meal recommendations
- **Context-aware**: Considers user preferences, goals, and feedback history
- **Time-based generation**: `/nextmeal` auto-detects meal type by time:
  - Before 11 AM → Breakfast
  - 11 AM - 3 PM → Lunch
  - 3 PM - 10 PM → Dinner
  - After 10 PM → Next day's breakfast
- **Automated delivery**: Sends plans at 6:30 AM, 10:30 AM, 3:30 PM

### 3. Meal Logging ✅
- **Free-form input**: `/logmeal I ate chicken and salad`
- **AI parsing**: Extracts dishes, quantities, meal type
- **Smart matching**: Matches to HUDS menu items
- **Nutrition tracking**: Calculates total calories and macros
- **Replaces proposals**: Updates proposed plans with actual consumption

### 4. Feedback System ✅
- **Easy input**: Reply to any meal plan message
- **AI extraction**: Determines rating (-2 to +2) from natural language
- **Time-weighted**: Recent feedback has more influence
- **Adaptive learning**: Improves recommendations over time
- **Decay rates**: Different half-lives based on rating intensity

### 5. Telegram Bot Interface ✅

#### User Commands
- `/start` - Register with automatic profile creation
- `/nextmeal` - Generate meal plan (time-aware)
- `/logmeal <text>` - Log actual meals with AI parsing
- `/preferences` - Set dietary restrictions
- `/goals` - Update nutritional targets
- `/today` - View today's meal plans
- `/feedback` - Reply to dishes for ratings
- `/history` - Review meal history
- `/help` - Show command list

#### Admin Commands
- `/fetch` - Interactive date picker for manual menu fetching
- `/stats` - System statistics and monitoring

### 6. Database Models ✅

#### menu.Dish
- Stores dish name, category, portion size
- 14+ nutritional fields (all floats, default 0.0)
- Ingredients list
- First/last seen date tracking

#### menu.DailyMenu
- Links dishes to specific date + meal type
- Unique constraint on (date, meal_type)
- Many-to-many relationship with dishes

#### users.UserProfile
- Extends Django User model
- Telegram integration (chat_id, username)
- Nutritional goals (calories, protein, carbs, fat, fiber, sodium, sugars)
- Dietary restrictions and preferences
- Notification settings per meal
- Admin flag for special commands

#### users.MealPlan
- AI-generated meal plan
- Links user to daily menu
- Dish quantities via MealPlanDish through-model
- Status tracking: pending → approved → completed
- AI explanation/tips text

#### users.MealHistory
- Records of consumed meals
- Quantity tracking
- Links to meal plans for context

#### users.UserFeedback
- Rating system: -2 to +2
- Time-weighted decay (different rates per rating)
- Free-form comments
- Linked to meal history

## 🚀 Deployment Architecture

### Railway Services (6)
```
├── Postgres (managed database)
├── Redis (managed cache)
├── App Service (Django + WhiteNoise)
│   ├── Runs migrations
│   ├── Creates superuser (admin/admin123)
│   ├── Sets up periodic tasks
│   └── Serves web app and admin
├── Worker Service (Celery worker)
│   └── Processes background tasks
├── Cron Service (Celery Beat)
│   └── Schedules periodic tasks
└── Bot Service (Telegram bot)
    └── Handles user interactions
```

### Local Development (7 services)
```
├── db (PostgreSQL)
├── redis
├── web (Django)
├── nginx (Reverse proxy)
├── celery-worker
├── celery-beat
└── telegram-bot
```

## 🔄 Complete Workflow

### Daily Automation Cycle

**11:00 PM** (Night Before)
1. Celery Beat triggers `fetch_tomorrow_menus`
2. Scrapes HUDS website for all meals
3. Parses nutritional data using BeautifulSoup
4. Stores in Dish and DailyMenu models

**6:30 AM** (Breakfast)
1. Celery Beat triggers `generate_and_send_meal_plans('breakfast')`
2. For each user with breakfast notifications:
   - Retrieves preferences, goals, and feedback
   - Calls AI to generate personalized plan
   - Creates MealPlan with recommended dishes
   - Sends formatted message via Telegram

**10:30 AM** (Lunch) - Same process for lunch

**3:30 PM** (Dinner) - Same process for dinner

### User Interaction Flow

1. **Registration**: `/start` → Creates User + UserProfile → Links Telegram chat_id

2. **Preference Setting**: `/preferences vegetarian, no pork` → Updates dietary_restrictions

3. **Manual Meal Request**: `/nextmeal` → AI generates plan based on current time

4. **Meal Logging**: 
   - `/logmeal I ate waffles and berries`
   - AI parses: "Waffles (1.0), Strawberries (1.0)"
   - Matches to menu items
   - Creates MealHistory records
   - Calculates nutrition totals

5. **Feedback**:
   - User replies: "Too sweet, prefer less sugar"
   - AI extracts rating: -1 (bad)
   - Creates UserFeedback record
   - Influences future meal plans

## 🛠️ Configuration

### Environment Variables
```env
# Database (Railway managed)
PGDATABASE, PGUSER, PGPASSWORD, PGHOST, PGPORT

# Or Docker Compose
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

# Required
TELEGRAM_BOT_TOKEN=<from @BotFather>
OPENAI_API_KEY=<from OpenAI>
DJANGO_SECRET_KEY=<random 50+ chars>

# Optional
OPENAI_MODEL=gpt-4
TIME_ZONE=America/New_York
DJANGO_DEBUG=False
```

### Meal Times (settings.py)
```python
BREAKFAST_TIME = '06:30'  # Auto-generated plan send time
LUNCH_TIME = '10:30'
DINNER_TIME = '15:30'
```

### Feedback Decay Rates (users/models.py)
```python
# UserFeedback.get_weighted_rating()
rating == -2: half_life = 180 days  # Never again
rating == -1: half_life = 90 days   # Bad
rating == 0:  half_life = 30 days   # Neutral
rating == 1:  half_life = 60 days   # Good
rating == 2:  half_life = 90 days   # Love it
```

## 📊 Key Metrics

### Database Scale
- **Dishes**: ~500-1000 unique dishes over time
- **DailyMenus**: 3 per day (90/month)
- **UserProfiles**: 1 per user
- **MealPlans**: Up to 3 per user per day
- **MealHistory**: Grows with activity
- **UserFeedback**: Time-weighted ratings

### Indexes
- `Dish.name` - Unique, indexed
- `DailyMenu.(date, meal_type)` - Unique together
- `UserProfile.telegram_chat_id` - Unique
- `UserFeedback.rating` - Indexed for aggregation
- `UserFeedback.feedback_date` - Indexed for time queries

## 🔧 Recent Bug Fixes & Improvements

### Fixed Issues ✅
1. **Celery Beat meal notifications** - Added synchronous `format_meal_plan()` function
2. **Nutrition parsing** - Fixed regex to correctly parse carbohydrates (e.g., "Total Carbohydrate.20.7g")
3. **Database queries** - Corrected `dailymenu__date__gte` to `menus__date__gte`
4. **Admin interface** - Added `is_admin` field to user profiles

### New Features ✅
1. **Interactive date picker** - `/fetch` command with clickable date buttons
2. **Time-based meal detection** - `/nextmeal` auto-detects meal type
3. **Meal logging** - `/logmeal` with AI parsing and nutrition tracking
4. **Admin commands** - `/fetch` and `/stats` for system management
5. **Automatic setup** - Auto-creates superuser and periodic tasks on Railway

## 🚦 Success Criteria (All Met)

✅ Fully automated menu fetching with nutrition data  
✅ AI-powered personalized meal planning  
✅ Telegram bot with interactive commands  
✅ Time-weighted feedback system  
✅ Meal logging with natural language processing  
✅ Railway deployment with zero-downtime updates  
✅ Complete admin interface  
✅ Automated task scheduling  
✅ Comprehensive documentation  

---

**Project Status**: 🎉 **PRODUCTION READY**

All core features implemented, tested, and deployed on Railway. The system is actively running and serving users with automated meal plans, intelligent recommendations, and comprehensive tracking.

**Recent Deployment**: Railway with managed PostgreSQL and Redis  
**Latest Updates**: Fixed Celery notifications, added meal logging, improved time-based detection  
**Documentation**: README.md, RAILWAY_QUICK_START.md, QUICKSTART.md
