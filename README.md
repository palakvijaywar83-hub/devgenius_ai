# DevGenius AI

> *"Jolly good code, old chap — but do you actually understand what it's doing?"*

**Understand Code. Fix Bugs. Learn Smarter.**
A Django-powered web application that brings the full intellectual rigour of a Cambridge tutor to your terminal window — minus the tweed jacket and the mildly condescending smile.

Built for Hackathon track **PS 01: AI for Learning & Developer Productivity**.

---

## What on Earth Does It Do?

Imagine, if you will, that you have a brilliantly well-read friend — the sort who reads compiler theory for leisure and corrects your Big-O notation over tea. That is DevGenius AI. It does not merely hand you answers; it explains the *reasoning*, like a proper mentor rather than a glorified search engine.

| Tool | What It Does |
|---|---|
| ?? **Code Explainer** | Pastes in your code, explains it step by step — beginner to advanced. No waffle, pure clarity. |
| ?? **Bug Debugger** | Finds the likely culprit, explains *why* it is wrong, and suggests a fix. Unverified, of course — one must always test. |
| ?? **AI Tutor** | Teaches any programming topic in your preferred style. Ask follow-up questions. Genuinely interactive. |
| ?? **Quiz Generator** | Generates a custom quiz, scores it server-side (no peeking at answers in the browser), and explains every question. |
| ?? **Docs Generator** | Turns your code or project description into clean Markdown documentation. Copy to clipboard in one click. |
| ?? **Progress Tracker** | Dashboard and progress page driven purely by real activity — no fabricated statistics, no flattery. |

---

## Quick Start

`ash
cd devgenius_ai
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
# Edit .env: set AI_PROVIDER and AI_API_KEY

python manage.py makemigrations tools
python manage.py migrate
python manage.py test          # 51 tests — all should pass
python manage.py runserver
`

Open **http://127.0.0.1:8000**, sign up, and have at it.

> Bootstrap and fonts load from CDNs — the browser needs internet access.

---

## Environment Variables (.env)

| Variable | Purpose |
|---|---|
| DJANGO_SECRET_KEY | Required when DJANGO_DEBUG=False. |
| DJANGO_DEBUG | True for local dev (default). |
| DJANGO_ALLOWED_HOSTS | Comma-separated hosts. |
| AI_PROVIDER | nthropic (default) or openai (any OpenAI-compatible API). |
| AI_API_KEY | Your provider key. ANTHROPIC_API_KEY / OPENAI_API_KEY also work. |
| AI_MODEL | Optional. Defaults: claude-sonnet-5-5 (Anthropic), gpt-4o-mini (OpenAI). |
| AI_BASE_URL | Optional. For OpenAI-compatible providers. |
| AI_TIMEOUT, AI_RATE_LIMIT_PER_MINUTE, MAX_CODE_CHARS | Limits (defaults: 60 s, 10/min, 8 000 chars). |

If no key is set, every AI page shows clear setup instructions. **Nothing is generated or faked.**

---

## Architecture

`
devgenius/    Project settings and URLs
accounts/     Registration, login, logout (Django auth)
core/         Landing page, dashboard, progress
tools/        Models, forms, views, prompts.py, ai_service.py, tests
templates/    Django templates (Bootstrap 5)
static/       CSS + JS
`

- **	ools/ai_service.py** — One reusable service. un(feature, data, user_key) builds a structured prompt, calls the provider over HTTPS, parses and validates JSON, and maps every failure mode (missing key, timeout, 429, bad credentials, 5xx, malformed output) to a typed AIServiceError with a safe user-facing message.
- **Models** — CodeExplanation, BugReport, LearningSession, Quiz / QuizQuestion / QuizAttempt, Documentation. Every query is filtered by equest.user; other users' records return 404.
- **Progress** — Computed from the database only. It reflects real activity (quiz accuracy, topics studied) — not a measure of coding mastery.

---

## Security

- CSRF on every form and the follow-up fetch endpoint
- Login required on all application pages
- POST-only deletes and logout
- Input length limits + per-user rate limiting (cache-backed)
- Request body size cap (DATA_UPLOAD_MAX_MEMORY_SIZE)
- AI output always HTML-escaped before rendering
- API key only from environment variables — never logged or sent to the browser
- **Submitted code is never executed** — it is sent to the AI as plain text; suggested fixes are clearly labelled *unverified*
- Quiz answers are scored server-side and never sent to the browser before submission

---

## Demo Workflow (3 Minutes)

1. Sign up ? dashboard shows empty states (no fake stats).
2. **Explain** — paste def mean(nums): return sum(nums)/len(nums) ? beginner level.
3. **Debug** — same code, error ZeroDivisionError, expected "return 0 for empty list".
4. **Tutor** — Python ? "list comprehensions" ? hands-on ? ask a follow-up question.
5. **Quiz** — Python / loops / 5 questions ? take it ? results with explanations.
6. **Docs** — paste code ? Copy to clipboard.
7. Dashboard and **Progress** now reflect your real activity.

---

## Technical Notes

- Django REST Framework was not needed; the one JSON endpoint (tutor follow-ups) is a plain Django view.
- For production: set DJANGO_DEBUG=False, a real DJANGO_SECRET_KEY, run collectstatic, and use a shared cache (e.g. Redis) so rate limiting works across processes.
- 51 tests covering AI service error handling, form validation, view workflows, quiz scoring, data isolation, and authentication.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 (Python 3.14) |
| Frontend | Bootstrap 5, vanilla JS |
| Database | SQLite (dev) / any Django-supported DB (prod) |
| AI | Anthropic Claude / OpenAI GPT (configurable) |
| Auth | Django built-in auth |
| Deployment | Any WSGI host (Gunicorn, uWSGI, etc.) |

---

*Made with excessive amounts of tea and a firm belief that developers deserve tools that actually explain things.*
