# HUDS Menu Planning System

A Dockerized Django application that fetches daily menus from Harvard University Dining Services (HUDS), generates personalized meal plans using AI, and delivers recommendations via Telegram bot.

## Features

- **Automated Menu Fetching**: Nightly scraping of HUDS website for next day's menus and nutritional data
- **AI-Powered Meal Planning**: Uses OpenAI GPT to generate balanced, personalized meal recommendations
- **Telegram Bot Interface**: Interactive bot for receiving meal plans and providing feedback
- **User Preferences**: Tracks dietary restrictions, nutritional goals, and food preferences
- **Feedback System**: Time-weighted rating system that learns user preferences over time
- **Comprehensive Database**: PostgreSQL database storing dishes, nutritional data, user profiles, meal history, and feedback

## Architecture

### Components

1. **Django Web Application** (`web` service)
   - REST API and admin interface
   - Database models for dishes, menus, users, and feedback
   - Business logic for meal planning

2. **PostgreSQL Database** (`db` service)
   - Stores all persistent data
   - Optimized indexes for common queries

3. **Redis** (`redis` service)
   - Message broker for Celery tasks
   - Caching layer

4. **Celery Worker** (`celery-worker` service)
   - Executes background tasks
   - Processes meal plan generation

5. **Celery Beat** (`celery-beat` service)
   - Schedules periodic tasks
   - Triggers nightly menu fetching
   - Sends meal notifications at configured times

6. **Telegram Bot** (`telegram-bot` service)
   - Handles user interactions
   - Sends meal plans
   - Collects feedback

7. **Nginx** (`nginx` service)
   - Reverse proxy for Django
   - Serves static files

### Apps

- **menu**: Manages dishes and daily menus
- **users**: User profiles, meal plans, history, and feedback
- **bot**: Telegram bot handlers and commands

### Key Workflows

#### 1. Daily Menu Fetching
- **When**: Every night (scheduled via Celery Beat)
- **What**: Fetches next day's breakfast, lunch, and dinner menus from HUDS
- **How**: Uses `huds_lib/webpage.py` and `huds_lib/parser.py` to scrape and parse
- **Storage**: Creates/updates `Dish` and `DailyMenu` models

#### 2. Meal Plan Generation
- **When**: 
  - Breakfast: 6:30 AM
  - Lunch: 10:30 AM
  - Dinner: 3:30 PM (15:30)
- **What**: Generates personalized meal plan for each user
- **How**: 
  1. Retrieves user's preferences and nutritional goals
  2. Fetches user's meal history and feedback
  3. Calls OpenAI API with context (`huds_lib/model.py`)
  4. Creates `MealPlan` with recommended dishes and quantities
  5. Sends plan via Telegram bot

#### 3. User Feedback Loop
- **When**: After meals (user-initiated)
- **What**: Collects feedback on dishes
- **How**:
  1. User provides free-form feedback via Telegram
  2. OpenAI structured output extracts rating (-2 to +2)
  3. Creates `UserFeedback` record with timestamp
  4. Time-weighted ratings influence future recommendations

## Setup

Choose your deployment method:

### 🚀 Quick Start (Local Development)

#### Prerequisites
- Docker and Docker Compose
- Telegram Bot Token (from @BotFather)
- OpenAI API Key

#### Installation

1. **Clone and navigate to project**:
   ```bash
   cd /path/to/HUDS
   ```

2. **Create environment file**:
   ```bash
   cp env.example .env
   ```

3. **Configure environment variables** in `.env`:
   ```env
   # Database
   POSTGRES_DB=huds_db
   POSTGRES_USER=huds_user
   POSTGRES_PASSWORD=your_secure_password

   # Django
   DJANGO_SECRET_KEY=your_django_secret_key
   DJANGO_DEBUG=True

   # Telegram Bot
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token

   # OpenAI
   OPENAI_API_KEY=your_openai_api_key

   # Timezone
   TIME_ZONE=America/New_York
   ```

4. **Build and start services**:
   ```bash
   docker-compose up --build
   ```

5. **Run migrations** (in a new terminal):
   ```bash
   docker-compose exec web python manage.py migrate
   ```

6. **Create superuser**:
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

7. **Access the application**:
   - Admin interface: http://localhost/admin
   - API: http://localhost/api/
   - Telegram bot: Search for your bot on Telegram

### ☁️ Railway Deployment (Recommended for Production)

**Railway is the recommended option** for production deployment with excellent multi-service support.

**Quick Start**: See **[RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)** for a 15-minute deployment guide.

**Detailed Guide**: See **[RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)** for comprehensive instructions.

Railway advantages:
- ✅ Easy multi-service deployment (App, Worker, Cron, Bot)
- ✅ Managed PostgreSQL and Redis databases
- ✅ Automatic deploys from GitHub
- ✅ Free trial + affordable pricing ($5/month hobby plan)
- ✅ Built-in monitoring and logging

### 🐳 Other Cloud Options

For alternative deployment platforms, see **[CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)** for:
- DigitalOcean App Platform
- Google Cloud Run
- AWS Elastic Beanstalk

## Usage

### Admin Interface

1. Navigate to http://localhost/admin
2. Login with superuser credentials
3. Manage:
   - Dishes and nutritional data
   - Daily menus
   - User profiles and preferences
   - Meal plans and history
   - User feedback

### Telegram Bot Commands

- `/start` - Register and set up your profile
- `/preferences` - Update dietary restrictions and preferences
- `/goals` - Set nutritional goals
- `/today` - Get today's meal plans
- `/feedback <meal>` - Provide feedback on a meal
- `/history` - View your meal history
- `/help` - Show available commands

### Management Commands

#### Fetch Daily Menu
```bash
docker-compose exec web python manage.py fetch_daily_menu --date 2025-09-30
```

Options:
- `--date`: Date to fetch (YYYY-MM-DD), defaults to tomorrow
- `--meals`: Specific meals (breakfast, lunch, dinner), defaults to all

#### Generate Meal Plans
```bash
docker-compose exec web python manage.py generate_meal_plans --meal breakfast
```

#### Send Notifications
```bash
docker-compose exec web python manage.py send_meal_notifications --meal breakfast
```

## Database Models

### menu.Dish
- Stores dish information and nutritional data
- All numerical fields default to 0.0 for missing data
- Tracks first and last appearance dates

### menu.DailyMenu
- Links to dishes available for a specific date and meal
- Unique constraint on (date, meal_type)

### users.UserProfile
- Extended user profile with nutritional goals
- Telegram integration fields
- Dietary preferences and restrictions

### users.MealPlan
- AI-generated meal plan for a user
- Links to dishes with quantities
- Tracks approval and completion status

### users.MealHistory
- Records of actually consumed meals
- Links to meal plans for tracking

### users.UserFeedback
- Time-weighted feedback system
- Ratings from -2 (never again) to +2 (love it)
- Different decay rates based on rating type

## Development

### Running Tests
```bash
docker-compose exec web python manage.py test
```

### Accessing Django Shell
```bash
docker-compose exec web python manage.py shell
```

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f telegram-bot
docker-compose logs -f celery-worker
```

### Database Backup
```bash
docker-compose exec db pg_dump -U huds_user huds_db > backup.sql
```

### Database Restore
```bash
cat backup.sql | docker-compose exec -T db psql -U huds_user huds_db
```

## Scheduled Tasks

Configured in Celery Beat (via Django admin or code):

1. **Fetch Tomorrow's Menus**: Daily at 11:00 PM
2. **Send Breakfast Plans**: Daily at 6:30 AM
3. **Send Lunch Plans**: Daily at 10:30 AM  
4. **Send Dinner Plans**: Daily at 3:30 PM

## Customization

### Meal Notification Times

Edit in `huds_project/settings.py`:
```python
BREAKFAST_TIME = '06:30'
LUNCH_TIME = '10:30'
DINNER_TIME = '15:30'
```

### Feedback Rating Decay

Modify `UserFeedback.get_weighted_rating()` in `users/models.py`:
```python
# Adjust half_life values (in days)
if self.rating == -2:
    half_life = 180  # 6 months
elif self.rating == -1:
    half_life = 90   # 3 months
# ... etc
```

### AI Model Selection

Edit `huds_lib/model.py`:
```python
def _get_default_model_name() -> str:
    return "gpt-4"  # or "gpt-3.5-turbo", etc.
```

## Troubleshooting

### Services won't start
- Check Docker logs: `docker-compose logs`
- Ensure all required ports are free (80, 5432, 6379, 8000)
- Verify environment variables in `.env`

### Database connection errors
- Ensure PostgreSQL service is healthy: `docker-compose ps`
- Check database credentials in `.env`
- Wait for database to be ready (healthcheck in docker-compose.yml)

### Telegram bot not responding
- Verify `TELEGRAM_BOT_TOKEN` in `.env`
- Check bot service logs: `docker-compose logs telegram-bot`
- Ensure bot service is running: `docker-compose ps`

### OpenAI API errors
- Verify `OPENAI_API_KEY` in `.env`
- Check API quota and billing
- Review OpenAI service status

## License

This project is for educational purposes.

## Credits

- HUDS Menu Scraping: Based on `HUDS_MVP` parser
- AI Meal Planning: OpenAI GPT integration
- Telegram Bot: python-telegram-bot library
