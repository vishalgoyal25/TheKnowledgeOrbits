# PHASE 0 - PROJECT SETUP GUIDE

**Complements:** ENGINE_BASED_EDTECH_COMPLETE_ARCHITECTURE.md
**Purpose:** Week 1 setup instructions
**Goal:** Get development environment ready

---

## REPOSITORY STRUCTURE

```
knowledgeorbit_v2/
├── backend/
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── content/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── services/
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── chunking.py
│   │   │   │   └── embedding.py
│   │   │   ├── api/
│   │   │   │   ├── views.py
│   │   │   │   ├── serializers.py
│   │   │   │   └── urls.py
│   │   │   └── tests/
│   │   │       └── test_content.py
│   │   ├── knowledge/
│   │   ├── assessment/
│   │   ├── user_state/
│   │   └── analytics/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── shared/
│   │   ├── utils/
│   │   ├── constants.py
│   │   └── exceptions.py
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── (routes)/
│   │   ├── components/
│   │   ├── lib/
│   │   └── styles/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.local.example
├── docs/
│   ├── ENGINE_BASED_EDTECH_COMPLETE_ARCHITECTURE.md
│   ├── CONTENT_ENGINE_IMPLEMENTATION.md
│   ├── ARTICLE_GENERATION_IMPLEMENTATION.md
│   └── CODING_STANDARDS.md
├── scripts/
│   ├── setup.sh
│   └── migrate.py
├── .gitignore
└── README.md
```

---

## BACKEND SETUP

### 1. Create Project (PowerShell)

```powershell
# Navigate to projects folder
cd D:\AI_Projects\

# Create directory
mkdir knowledgeorbit_v2
cd knowledgeorbit_v2

# Create backend folder
mkdir backend
cd backend

# Create virtual environment
python -m venv myenv

# Activate
.\myenv\Scripts\Activate

# Upgrade pip
python -m pip install --upgrade pip
```

### 2. Install Dependencies

```powershell
# Create requirements.txt
New-Item requirements.txt

# Add to requirements.txt:
Django==5.0.6
djangorestframework==3.15.2
djangorestframework-simplejwt==5.3.1
psycopg2-binary==2.9.9
pgvector==0.2.5
python-dotenv==1.0.0
Pillow==10.3.0
groq==0.9.0
sentence-transformers==2.7.0
pdfplumber==0.11.0
pytesseract==0.3.10
feedparser==6.0.11
celery==5.4.0
redis==5.0.4
django-cors-headers==4.3.1

# Install
pip install -r requirements.txt
```

### 3. Initialize Django

```powershell
# Create project
django-admin startproject config .

# Create engines folder
mkdir engines
New-Item engines\__init__.py

# Create first engine
python manage.py startapp content engines/content

# Remove default apps/ folder if exists
```

### 4. Configure Settings

**config/settings/base.py:**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    # Engines
    'engines.content',
    'engines.knowledge',
    'engines.assessment',
    'engines.user_state',
    'engines.analytics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'knowledgeorbit'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
]
```

**config/settings/development.py:**

```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
```

**config/settings/production.py:**

```python
from .base import *

DEBUG = False
ALLOWED_HOSTS = [os.getenv('ALLOWED_HOSTS', '').split(',')]
```

### 5. Environment Variables

**Create .env:**

```powershell
New-Item .env

# Add to .env:
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=knowledgeorbit
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
GROQ_API_KEY=your-groq-key
```

### 6. Database Setup (PostgreSQL)

```powershell
# Connect to PostgreSQL
psql -U postgres

# In psql:
CREATE DATABASE knowledgeorbit;
CREATE EXTENSION IF NOT EXISTS vector;
\q

# Back in PowerShell, run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 7. Test Server

```powershell
# Run server
python manage.py runserver

# Visit: http://localhost:8000/admin
```

---

## FRONTEND SETUP

### 1. Create Next.js App

```powershell
# Open new terminal
cd D:\AI_Projects\knowledgeorbit_v2

# Create Next.js app
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir

# Navigate
cd frontend

# Install additional dependencies
npm install axios @tanstack/react-query lucide-react
npx shadcn-ui@latest init
```

### 2. Environment Variables

**Create .env.local:**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Test Frontend

```powershell
npm run dev

# Visit: http://localhost:3000
```

---

## CRITICAL RULES

### Database Migrations

```powershell
# ALWAYS run in this order:
python manage.py makemigrations
python manage.py migrate

# If stuck, NEVER edit migrations manually
# Instead: Delete migration files, recreate
```

### Coding Standards

- UUID primary keys (ALWAYS)
- Type hints (ALWAYS)
- Docstrings (ALWAYS)
- help_text on model fields (ALWAYS)
- Table names: enginename_modelname

### Git Setup

```powershell
git init
git add .
git commit -m "feat: initial project setup"
```

**.gitignore:**

```
# Python
*.pyc
__pycache__/
myenv/
.env

# Node
node_modules/
.next/
.env.local

# IDE
.vscode/
.idea/
```

---

## VERIFICATION CHECKLIST

**Backend:**

- [ ] Django server runs (http://localhost:8000)
- [ ] Admin accessible (http://localhost:8000/admin)
- [ ] Database connected (no errors)
- [ ] Migrations applied

**Frontend:**

- [ ] Next.js runs (http://localhost:3000)
- [ ] API URL configured (.env.local)
- [ ] Tailwind working

**Structure:**

- [ ] engines/ folder exists
- [ ] config/settings/ structure correct
- [ ] .env files created (not committed)
- [ ] .gitignore in place

---

## NEXT STEPS

**After setup complete:**

1. Read CONTENT_ENGINE_IMPLEMENTATION.md
2. Build Content Engine models (Week 2)
3. Implement ingestion service
4. Test with sample PDF

---

## TROUBLESHOOTING

**PostgreSQL connection error:**

```powershell
# Check PostgreSQL is running
# Verify credentials in .env
# Test connection: psql -U postgres -d knowledgeorbit
```

**Migration conflicts:**

```powershell
# Nuclear option (development only):
python manage.py migrate --fake
# Or delete db, recreate, migrate fresh
```

**Import errors:**

```powershell
# Ensure virtual environment activated
# Reinstall requirements: pip install -r requirements.txt
```

---

**END OF SETUP GUIDE**

**Status after Phase 0: Development environment ready for Week 2 (Content Engine)**
