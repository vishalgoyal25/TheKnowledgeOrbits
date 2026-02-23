# 🌍 TheKnowledgeOrbits

**AI-Powered Ed-Tech Platform for UPSC Aspirants**
_Engine-First Architecture | Scalable to 10M+ Users | Built by Solo Developer_

---

## 📋 Overview

TheKnowledgeOrbits is a next-generation educational platform designed specifically for UPSC Civil Services Examination preparation. Built using innovative **engine-first architecture**, it combines static educational content (NCERT books) with real-time current affairs to generate contextual, AI-powered learning materials.

### 🎯 Core Innovation

**Chunk-Based Content Architecture:**

- All content (PDFs, articles, news) broken into semantic chunks
- AI generates articles by combining static chunks + current affairs chunks
- Quizzes generated from chunks, not articles
- Enables dynamic, context-aware content generation

**33-Engine Architecture:**

- Each engine = one clear responsibility
- Engines communicate via events, not direct calls
- Independently scalable and testable
- Products are thin layers composing multiple engines

---

## ✨ Key Features

### 📚 Content Management

- **Smart Ingestion:** PDF upload with OCR support (scanned documents)
- **Semantic Chunking:** Intelligent 1200-character chunks with context preservation
- **Multi-Format Support:** PDFs, videos, web content, audio

### 📰 Current Affairs Integration

- **Daily News Scraping:** Automated RSS monitoring (The Hindu, Indian Express)
- **Contextual Linking:** AI links current affairs to static syllabus topics
- **Integrated Articles:** Theory from NCERT + Recent examples from news

### 🧠 AI-Powered Learning

- **Article Generation:** GROQ-powered narrative creation from chunks
- **Quiz Generation:** MCQs with explanations from source chunks
- **Personalized Paths:** Learning paths based on weak areas
- **AI Tutor:** Conversational doubt resolution

### 📊 Progress Tracking

- **Event Sourcing:** Complete audit trail of user actions
- **Topic Mastery:** Per-topic skill scoring (0-100)
- **Adaptive Difficulty:** Questions calibrated to user level
- **Streak Management:** Daily learning habit tracking

### 🎓 Assessment System

- **Practice Quizzes:** Topic-wise MCQ practice
- **Mock Tests:** Full exam simulation with timing
- **Detailed Analytics:** Section-wise performance breakdown
- **Rank Prediction:** ML-based rank forecasting

### 🎮 Engagement Features

- **Gamification:** Achievements, badges, leaderboards
- **Spaced Repetition:** Flashcards with SM-2 algorithm
- **Collaboration:** Discussion forums, study groups
- **Bookmarks & Notes:** Personal knowledge management

---

## 🏗️ Architecture

### Technology Stack

**Backend:**

- Python 3.11+
- Django 5.0 + Django REST Framework 3.15
- PostgreSQL 16 + pgvector (vector search)
- Redis 7.0 (caching)
- Celery 5.0 (async tasks)

**AI/ML:**

- GROQ API (article/quiz generation)
- sentence-transformers (embeddings)
- Whisper API (transcription)
- Tesseract/PaddleOCR (OCR)

**Frontend:**

- Next.js 16 (App Router)
- TypeScript
- shadcn/ui + Tailwind CSS
- TanStack Query

**Infrastructure:**

- Backend: Render
- Frontend: Vercel
- Database: Supabase
- CDN: Cloudinary
- Monitoring: Sentry
- Analytics: PostHog

### 33 Engines (Organized by Layer)

**L0 - Data Ingestion:**

- Content Engine
- Current Affairs Engine

**L1 - Organization:**

- Knowledge Engine
- Search Engine

**L2 - Generation:**

- Article Generation Engine
- Assessment Engine
- Video Engine

**L3 - User Tracking:**

- User State Engine

**L4 - Analysis:**

- Analytics Engine

**L5 - Intelligence:**

- Personalization Engine
- Prediction Engine
- AI Tutor Engine

**L6 - Engagement:**

- Gamification Engine
- Collaboration Engine
- Revision Engine

**L7 - Operations:**

- Authentication Engine
- Authorization Engine
- Notification Engine
- Storage Engine
- Cache Engine

**L8 - Growth:**

- Commerce Engine
- Marketing Engine
- Onboarding Engine
- Retention Engine

**L9 - Advanced:**

- Mock Test Engine
- NLP Engine
- Computer Vision Engine
- Voice Engine

**L10 - Enterprise:**

- Marketplace Engine
- White-label Engine
- Content Moderation Engine
- Privacy Engine
- Reporting Engine

---

## 🚀 Quick Start

### Prerequisites

```bash
# System Requirements
- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Redis 7.0
- Git
```

### Backend Setup

```bash
# Clone repository
git clone https://github.com/yourusername/TheKnowledgeOrbits.git
cd TheKnowledgeOrbits/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
copy .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Setup environment variables
copy .env.example .env.local
# Edit .env.local with your configuration

# Start development server
npm run dev
```

### Access Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/api/v1/
- **Admin Panel:** http://localhost:8000/admin/

---

## 📚 Documentation

Comprehensive documentation available in `/docs`:

- **[Architecture Guide](docs/ARCHITECTURE.md)** - System design and engine architecture
- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Database Schema](docs/DATABASE_SCHEMA.md)** - Database design and relationships
- **[Coding Standards](docs/CODING_STANDARDS.md)** - Development guidelines
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment
- **[Contributing Guide](docs/CONTRIBUTING.md)** - How to contribute

---

## 🛣️ Development Roadmap

### Phase 0: Setup (Week 1) ✅

- Repository structure
- Django + DRF skeleton
- Next.js + TypeScript skeleton
- Docker development environment

### Phase 1: Core Engines (Weeks 2-4) 🔄

- Content Engine (PDF ingestion, chunking)
- Knowledge Engine (syllabus, topics)
- Assessment Engine (quiz generation)
- User State Engine (progress tracking)
- Analytics Engine (aggregation)

### Phase 2: Generation (Weeks 5-7)

- Article Generation Engine
- Current Affairs Engine
- Integrated article generation

### Phase 3: Frontend (Weeks 8-10)

- Authentication UI
- Article reading interface
- Quiz interface
- Dashboard

### Phase 4: Launch (Weeks 11-12)

- Content population (NCERT books)
- Production deployment
- Public beta launch

### Phase 5-10: Advanced Features (Weeks 13-36)

- Monetization (Commerce Engine)
- Engagement (Gamification, Collaboration)
- Intelligence (Personalization, AI Tutor)
- Advanced Content (Video, NLP, CV)
- Growth (Marketing, Retention)
- Enterprise (Marketplace, White-label)

---

## 🎯 Project Vision

### Problem Statement

UPSC aspirants struggle with:

- Disconnected static content and current affairs
- Generic study materials (not personalized)
- Lack of progress tracking and adaptive learning
- Time-consuming manual content organization

### Solution

TheKnowledgeOrbits provides:

- **Integrated Learning:** Static theory + current affairs in one narrative
- **AI-Powered Personalization:** Learning paths based on weak areas
- **Complete Tracking:** Event-sourced progress with topic mastery
- **Scalable Architecture:** Engine-first design for 10M+ users

### Target Users

- UPSC Civil Services aspirants
- State PSC candidates
- Competitive exam students
- Lifelong learners

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Standards

- Follow [CODING_STANDARDS.md](docs/CODING_STANDARDS.md)
- Write tests for all new features
- Maintain >80% code coverage
- Use type hints in Python
- Document all APIs

---

## 📊 Current Status

**Version:** 0.1.0-alpha
**Phase:** Phase 0 Complete, Phase 1 In Progress
**Test Coverage:** 85%
**Engines Built:** 5/33
**Status:** MVP Development

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Developed by:** Solo Developer
**Project Start:** January 2026
**Goal:** Production-ready platform for 10M+ users

---

## 🙏 Acknowledgments

- **GROQ:** AI-powered content generation
- **PostgreSQL Team:** pgvector extension for semantic search
- **Django Community:** Excellent web framework
- **Next.js Team:** Modern React framework
- **Open Source Community:** Countless libraries and tools

---

## 📞 Contact & Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/TheKnowledgeOrbits/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/TheKnowledgeOrbits/discussions)
- **Email:** support@TheKnowledgeOrbits.com
- **Twitter:** @KnowledgeOrbits

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/TheKnowledgeOrbits&type=Date)](https://star-history.com/#yourusername/TheKnowledgeOrbits&Date)

---

**Built with ❤️ for UPSC aspirants worldwide**

_Empowering learners through intelligent, contextual education_
