# COMPLETE_FOLDER_STRUCTURE.md

## TheKnowledgeOrbits — Complete Code File Hierarchy

**PKB File #7 | Version: 3.0 | Date: March 2026**

> This file lists **every `.py`, `.ts`, and `.tsx` source file** in the project.
> Config, docs, and non-code files are excluded for clarity.

---

## 1. ROOT SCRIPTS

```
TheKnowledgeOrbits/
├── scripts/
│   ├── seed_data.py
│   └── setup.sh
└── deepcheck.ps1
```

---

## 2. BACKEND — ALL `.py` FILES

### 2.1 Core (Django Project Root)

```
backend/
├── manage.py
├── conftest.py
│
└── core/
    ├── __init__.py
    ├── asgi.py
    ├── wsgi.py
    ├── urls.py
    ├── middleware.py
    ├── pagination.py
    └── settings/
        ├── __init__.py
        ├── base.py
        ├── development.py
        └── production.py
```

### 2.2 Auth Engine

```
engines/auth/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── email_service.py
│   └── token_service.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.3 Authorization Engine

```
engines/authorization/
├── __init__.py
├── admin.py
├── apps.py
├── decorators.py
├── middleware.py
├── models.py
├── permissions.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   └── permission_service.py
├── migrations/
│   └── __init__.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_permissions.py
    ├── test_services.py
    └── test_views.py
```

### 2.4 Content Engine

```
engines/content/
├── __init__.py
├── admin.py
├── apps.py
├── events.py
├── models.py
├── pagination.py
├── serializers.py
├── tasks.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── chunking_service.py
│   ├── embedding_service.py
│   └── ingestion_service.py
├── management/commands/
│   └── clean_content_engine.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.5 Knowledge Engine

```
engines/knowledge/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── mapping_service.py
│   └── search_service.py
├── management/commands/
│   └── seed_upsc_syllabus.py
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   └── 0002_topic_knowledge_t_module__67ee34_idx_and_more.py
└── tests/
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.6 Assessment Engine

```
engines/assessment/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   └── quiz_generator.py
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   ├── 0002_add_ownership.py
│   ├── 0002_delete_topicmastery.py
│   ├── 0003_merge_0002_add_ownership_0002_delete_topicmastery.py
│   ├── 0004_remove_quiz_quiz_created_by_idx_and_more.py
│   ├── 0005_fix_user_uuid_fields.py
│   ├── 0006_force_uuid_cast.py
│   └── 0007_remove_quiz_assessment__topic_i_655e08_idx_and_more.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.7 User State Engine

```
engines/userstate/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── activity_service.py
│   ├── bookmark_service.py
│   ├── mastery_service.py
│   └── progress_service.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.8 Analytics Engine

```
engines/analytics/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── analytics_service.py
│   ├── dashboard_service.py
│   └── insights_service.py
├── management/commands/
│   └── aggregate_daily.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.9 Article Generation Engine

```
engines/article_generation/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── tasks.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   └── generation_service.py
├── management/commands/
│   └── backfill_articles.py
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   ├── 0002_add_ownership.py
│   ├── 0003_remove_article_article_created_by_idx_and_more.py
│   ├── 0004_fix_article_gen_user_uuids.py
│   └── 0005_remove_article_article_art_topic_i_8b3c45_idx_and_more.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.10 Current Affairs Engine

```
engines/current_affairs/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── tasks.py
├── urls.py
├── views.py
├── services/
│   ├── __init__.py
│   ├── ca_processor.py
│   ├── rss_scraper.py
│   └── topic_linker.py
├── management/commands/
│   ├── __init__.py
│   ├── cleanup_expired.py
│   ├── scrape_ca.py
│   └── setup_automation.py
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   ├── 0002_remove_caarticle_ca_article_source__bbe5f0_idx_and_more.py
│   └── 0003_caarticle_ca_article_source__547539_idx.py
└── tests/
    ├── __init__.py
    ├── test_integration.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

### 2.11 Support Engine

```
engines/support/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── serializers.py
├── urls.py
├── views.py
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

### 2.12 Shared Engine Services

```
engines/shared/
├── services/
│   ├── __init__.py
│   ├── cache_service.py
│   └── visibility_service.py
└── tests/
    └── test_visibility_service.py
```

### 2.13 Shared (Root-Level)

```
backend/shared/
├── __init__.py
└── tests/
    └── factories.py
```

---

## 3. FRONTEND — ALL `.ts` & `.tsx` FILES

### 3.1 Root Config Files

```
frontend/
├── instrumentation.ts
├── next.config.ts
├── tailwind.config.ts
├── jest.config.ts
├── jest.setup.ts
├── sentry.client.config.ts
├── sentry.edge.config.ts
└── sentry.server.config.ts
```

### 3.2 Source Root

```
src/
├── proxy.ts
└── dummy.test.ts
```

### 3.3 Pages — App Router (`src/app/`)

```
app/
├── layout.tsx
├── page.tsx
│
├── auth/
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── verify/[token]/page.tsx
│   ├── forgot-password/page.tsx
│   └── reset-password/[token]/page.tsx
│
├── dashboard/
│   ├── layout.tsx
│   └── page.tsx
│
├── articles/
│   ├── page.tsx
│   ├── articles-client.tsx
│   ├── history/page.tsx
│   └── [id]/
│       ├── page.tsx
│       ├── private-article-fallback.tsx
│       └── sources/page.tsx
│
├── assessment/
│   ├── page.tsx
│   ├── generate/page.tsx
│   ├── history/page.tsx
│   ├── [id]/page.tsx
│   └── results/[attemptId]/page.tsx
│
├── current-affairs/
│   ├── page.tsx
│   ├── ca-client.tsx
│   ├── sources/page.tsx
│   ├── chunks/page.tsx
│   └── [id]/page.tsx
│
├── topics/
│   ├── page.tsx
│   ├── topics-client.tsx
│   └── [id]/
│       ├── page.tsx
│       └── articles/page.tsx
│
├── subjects/[id]/page.tsx
├── modules/[id]/page.tsx
├── bookmarks/page.tsx
├── notebook/
│   ├── page.tsx
│   └── new/page.tsx
├── generate/page.tsx
├── search/page.tsx
├── profile/page.tsx
├── settings/page.tsx
├── admin/ingest/page.tsx
├── health/page.tsx
├── about/page.tsx
├── contact/page.tsx
├── privacy/page.tsx
├── terms/page.tsx
├── cookies/page.tsx
└── api/revalidate/route.ts
```

### 3.4 Components (`src/components/`)

```
components/
├── articles/
│   ├── article-card.tsx
│   ├── article-content.tsx
│   ├── article-header.tsx
│   ├── article-metadata.tsx
│   ├── article-reader.tsx
│   ├── article-skeleton.tsx
│   ├── article-timeline.tsx
│   ├── bookmark-button.tsx
│   ├── reading-progress.tsx
│   ├── reading-progress-tracker.tsx
│   ├── related-articles.tsx
│   └── source-viewer.tsx
│
├── auth/
│   ├── ForgotPasswordForm.tsx
│   ├── LoginForm.tsx
│   ├── ProtectedRoute.tsx
│   ├── RegisterForm.tsx
│   ├── ResetPasswordForm.tsx
│   └── UserMenu.tsx
│
├── bookmarks/
│   ├── BookmarkCard.tsx
│   ├── BookmarkList.tsx
│   ├── BookmarkTabs.tsx
│   ├── EditNotesDialog.tsx
│   └── RemoveBookmarkDialog.tsx
│
├── charts/
│   ├── LineChart.tsx
│   └── ProgressBar.tsx
│
├── current-affairs/
│   ├── ca-article-card.tsx
│   ├── ca-chunk-card.tsx
│   ├── ca-filter-bar.tsx
│   ├── ca-source-status.tsx
│   ├── ca-timeline.tsx
│   └── ca-topic-badge.tsx
│
├── dashboard/
│   ├── DashboardOverview.tsx
│   ├── InsightsSection.tsx
│   ├── PerformanceChart.tsx
│   ├── RecentActivity.tsx
│   ├── RecentQuizzes.tsx
│   ├── stats-cards.tsx
│   ├── StatsCard.tsx
│   └── TopicMasterySection.tsx
│
├── generate/
│   ├── generation-form.tsx
│   ├── generation-progress.tsx
│   └── topic-selector.tsx
│
├── layout/
│   ├── footer.tsx
│   ├── header.tsx
│   ├── layout-content.tsx
│   ├── Navigation.tsx
│   └── sidebar.tsx
│
├── modules/
│   └── module-card.tsx
│
├── notebook/
│   ├── ArticleCard.tsx
│   ├── ArticleList.tsx
│   ├── DeleteArticleDialog.tsx
│   ├── EmptyState.tsx
│   ├── SearchBar.tsx
│   └── TopicFilter.tsx
│
├── providers/
│   ├── query-provider.tsx
│   └── sidebar-provider.tsx
│
├── quiz/
│   ├── attempt-card.tsx
│   ├── question-display.tsx
│   ├── question-palette.tsx
│   ├── quiz-card.tsx
│   ├── quiz-filters.tsx
│   ├── result-analysis.tsx
│   ├── result-card.tsx
│   ├── source-attribution.tsx
│   └── timer.tsx
│
├── search/
│   ├── search-bar.tsx
│   ├── search-filters.tsx
│   └── search-results.tsx
│
├── shared/
│   ├── empty-state.tsx
│   ├── engine-stats.tsx
│   ├── error-message.tsx
│   ├── GlobalErrorBoundary.tsx
│   └── loading.tsx
│
├── support/
│   └── feedback-button.tsx
│
├── topics/
│   ├── breadcrumb-nav.tsx
│   ├── topic-card.tsx
│   └── topic-tree.tsx
│
└── ui/                             # shadcn/ui (30 primitives)
    ├── accordion.tsx
    ├── alert-dialog.tsx
    ├── alert.tsx
    ├── avatar.tsx
    ├── badge.tsx
    ├── breadcrumb.tsx
    ├── button.tsx
    ├── calendar.tsx
    ├── card.tsx
    ├── checkbox.tsx
    ├── dialog.tsx
    ├── dropdown-menu.tsx
    ├── form.tsx
    ├── input.tsx
    ├── label.tsx
    ├── popover.tsx
    ├── progress.tsx
    ├── radio-group.tsx
    ├── scroll-area.tsx
    ├── select.tsx
    ├── separator.tsx
    ├── sheet.tsx
    ├── skeleton.tsx
    ├── slider.tsx
    ├── switch.tsx
    ├── table.tsx
    ├── tabs.tsx
    ├── textarea.tsx
    ├── toast.tsx
    ├── toaster.tsx
    └── tooltip.tsx
```

### 3.5 Hooks (`src/hooks/`)

```
hooks/
└── use-toast.ts
```

### 3.6 Lib — API & Logic (`src/lib/`)

```
lib/
├── api.ts
├── logger.ts
├── types.ts
├── utils.ts
│
├── api/
│   ├── client.ts
│   ├── analytics.ts
│   ├── articles.ts
│   ├── auth.ts
│   ├── bookmarks.ts
│   ├── current-affairs.ts
│   ├── notebook.ts
│   ├── quiz.ts
│   ├── search.ts
│   ├── server-hierarchy.ts
│   ├── subjects.ts
│   ├── support.ts
│   ├── topics.ts
│   └── userstate.ts
│
├── auth/
│   ├── AuthContext.tsx
│   ├── AuthProvider.tsx
│   ├── token-manager.ts
│   └── useAuth.ts
│
├── hooks/
│   ├── use-article.ts
│   ├── use-article-generation.ts
│   ├── use-auth.ts
│   ├── use-bookmark-toggle.ts
│   ├── use-bookmarks.ts
│   ├── use-current-affairs.ts
│   ├── use-dashboard.ts
│   ├── use-document.ts
│   ├── use-insights.ts
│   ├── use-notebook.ts
│   ├── use-quiz.ts
│   ├── use-reading-progress.ts
│   ├── use-search.ts
│   ├── use-subjects.ts
│   └── use-topics.ts
│
└── utils/
    └── markdown.ts
```

### 3.7 Types (`src/types/`)

```
types/
├── dashboard.ts
└── notebook.ts
```

---

## 4. FILE COUNT SUMMARY

| Area                      | .py files | .ts/.tsx files |
| ------------------------- | --------- | -------------- |
| Backend Core              | 10        | —              |
| Auth Engine               | 12        | —              |
| Authorization Engine      | 15        | —              |
| Content Engine            | 16        | —              |
| Knowledge Engine          | 14        | —              |
| Assessment Engine         | 18        | —              |
| User State Engine         | 15        | —              |
| Analytics Engine          | 15        | —              |
| Article Generation Engine | 16        | —              |
| Current Affairs Engine    | 19        | —              |
| Support Engine            | 9         | —              |
| Shared Services           | 4         | —              |
| Frontend Pages            | —         | 36             |
| Frontend Components       | —         | 90             |
| Frontend Lib/API/Hooks    | —         | 34             |
| Frontend Config           | —         | 8              |
| **TOTAL**                 | **~163**  | **~168**       |
