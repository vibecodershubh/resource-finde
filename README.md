# Resource Compass (Student Resource Finder)

A platform for students who are frustrated trying to find high-quality learning resources for specific topics.

It searches:
- Google Custom Search (for high-quality web/blog/video links)
- Reddit posts (for community-recommended resources)

And includes:
- Gemini AI Study Coach chatbot for study plans and next-step recommendations

## Features

- Topic-based resource discovery
- Format filtering (`all`, `video`, `blog`)
- Heuristic ranking score for quality signals
- AI chat assistant using Gemini API
- Responsive, modern UI for desktop and mobile

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create env file:

```bash
copy .env.example .env
```

3. Fill API keys in `.env`:

- `GOOGLE_API_KEY`
- `GOOGLE_CSE_ID`
- `GEMINI_API_KEY`

## Run

```bash
python app.py
```

Open `http://localhost:5000`

## Notes

- Google results require a Google Custom Search Engine (CSE).
- Reddit endpoint is public but can rate limit if overused.
- If Gemini key is missing, search still works, but AI chat returns a clear error.
