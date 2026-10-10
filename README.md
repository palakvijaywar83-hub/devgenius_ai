# DevGenius AI

**Understand Code. Fix Bugs. Learn Smarter.** — Hackathon track *PS 01: AI for Learning & Developer Productivity*.

A Django web app with an AI code explainer, bug detector, interactive tutor, quiz generator, documentation generator, per-user history and a progress page. The AI explains the *reasoning*, not just the answer.

## Quick start

```bash
cd devgenius_ai
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # Windows: copy .env.example .env
# edit .env: set AI_PROVIDER and AI_API_KEY (see below)

python manage.py makemigrations tools   # creates tools/migrations/0001_initial.py
python manage.py migrate
python manage.py test                   # run the test suite
python manage.py runserver
```

Open http://127.0.0.1:8000, sign up, and try the tools. (`createsuperuser` is optional; admin lives at `/admin/`.)

> The bootstrap and fonts load from CDNs, so the browser needs internet access.

## Environment variables (`.env`)

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required when `DJANGO_DEBUG=False`. |
| `DJANGO_DEBUG` | `True` for local dev (default). |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts. |
| `AI_PROVIDER` | `anthropic` (default) or `openai` (any OpenAI-compatible API). |
| `AI_API_KEY` | Your provider key. `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` also work. |
| `AI_MODEL` | Optional. Defaults: `claude-sonnet-5-5` (anthropic), `gpt-4o-mini` (openai). Use any model your key can access. |
| `AI_BASE_URL` | Optional. For OpenAI-compatible providers. |
| `AI_TIMEOUT`, `AI_RATE_LIMIT_PER_MINUTE`, `MAX_CODE_CHARS` | Limits (defaults 60s, 10/min, 8000 chars). |

If no key is set, every AI page shows setup instructions and **nothing is generated or faked**.

## Architecture

```
devgenius/   project settings, urls
accounts/    registration, login, logout (Django auth)
core/        landing page, dashboard, progress
tools/       models, forms, views, prompts.py, ai_service.py, tests
templates/   Django templates (Bootstrap 5)   static/   css + js
```

* `tools/ai_service.py` — one reusable service. `run(feature, data, user_key)` builds a structured prompt (`prompts.py`), calls the provider over its official HTTP API, parses and validates JSON, and maps failures (missing key, timeout, 429, bad key, 5xx, invalid output) to `AIServiceError` subclasses with safe user messages.
* Models: `CodeExplanation`, `BugReport`, `LearningSession`, `Quiz`/`QuizQuestion`/`QuizAttempt`, `Documentation`. Every query is filtered by `request.user`; other users' records return 404.
* Dashboard and progress numbers are computed from the database only. Progress is an activity record (quiz accuracy, topics practised) — **not** a measure of coding mastery.

## Security notes

CSRF on all forms (and the follow-up fetch), login required on all app pages, POST-only deletes/logout, input length limits + per-user rate limit, request body size cap, AI output always HTML-escaped, API key only from the environment and never logged or sent to the browser. **Submitted code is never executed**; it is sent to the AI as text, so suggested fixes are labelled *unverified*. Quiz answers are never sent to the browser before submission and are scored on the server.

## Demo workflow (3 minutes)

1. Sign up → dashboard shows empty states (no fake stats).
2. **Explain**: paste `def mean(nums): return sum(nums)/len(nums)` → beginner level.
3. **Debug**: same code, error `ZeroDivisionError: division by zero`, expected "return 0 for empty list".
4. **Tutor**: Python → "list comprehensions" → hands-on → ask a follow-up.
5. **Quiz**: Python / loops / 5 questions → take it → results with explanations.
6. **Docs**: paste code → Copy to clipboard.
7. Dashboard and **Progress** now reflect your real activity.

## Notes

* Django REST Framework wasn't needed; the one JSON endpoint (tutor follow-ups) is a plain Django view.
* For production: set `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY`, run `collectstatic`, and use a shared cache (e.g. Redis) so rate limiting works across processes.
