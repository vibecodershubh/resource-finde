import os
import re
from typing import Dict, List
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

REDDIT_HEADERS = {
    "User-Agent": "study-resource-finder/1.0 (by /u/resource-bot)"
}

VIDEO_DOMAINS = {"youtube.com", "www.youtube.com", "youtu.be", "vimeo.com", "www.vimeo.com"}
BLOG_HINTS = {"blog", "medium.com", "dev.to", "substack", "hashnode"}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return base.rstrip("/").lower()


def detect_format(url: str, title: str, snippet: str) -> str:
    text = f"{url} {title} {snippet}".lower()
    parsed = urlparse(url)

    if parsed.netloc.lower() in VIDEO_DOMAINS or "video" in text or "watch" in text:
        return "video"

    if any(hint in text for hint in BLOG_HINTS):
        return "blog"

    return "article"


def score_resource(item: Dict) -> float:
    text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    score = 0.0

    quality_terms = [
        "guide", "tutorial", "complete", "beginner", "advanced", "explained", "best", "roadmap"
    ]

    score += sum(1 for term in quality_terms if term in text) * 1.5

    if item.get("source") == "google":
        score += 5

    if item.get("source") == "reddit":
        score += min(item.get("upvotes", 0) / 100.0, 3)

    if item.get("format") == "video":
        score += 1

    if item.get("format") == "blog":
        score += 1

    return round(score, 2)


def search_google(topic: str, resource_type: str, limit: int) -> List[Dict]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    query = topic
    if resource_type == "video":
        query = f"{topic} best tutorial site:youtube.com OR site:vimeo.com"
    elif resource_type == "blog":
        query = f"{topic} best blog guide -site:youtube.com -site:vimeo.com"

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": max(1, min(limit, 10)),
    }

    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    resources: List[Dict] = []
    for item in data.get("items", []):
        link = item.get("link", "")
        title = item.get("title", "Untitled")
        snippet = item.get("snippet", "")

        detected_type = detect_format(link, title, snippet)
        if resource_type in {"video", "blog"} and detected_type != resource_type:
            continue

        resources.append({
            "title": title,
            "url": link,
            "snippet": snippet,
            "source": "google",
            "format": detected_type,
            "domain": urlparse(link).netloc,
        })

    return resources


def search_reddit(topic: str, resource_type: str, limit: int) -> List[Dict]:
    query = f"{topic} best resources tutorial"

    params = {
        "q": query,
        "sort": "relevance",
        "t": "all",
        "limit": max(5, min(limit * 2, 30)),
        "type": "link",
    }

    try:
        response = requests.get(
            "https://www.reddit.com/search.json",
            headers=REDDIT_HEADERS,
            params=params,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    resources: List[Dict] = []
    children = data.get("data", {}).get("children", [])

    for child in children:
        post = child.get("data", {})
        url = post.get("url_overridden_by_dest") or post.get("url")

        if not url or not re.match(r"^https?://", url):
            continue

        title = post.get("title", "Reddit recommendation")
        snippet = post.get("selftext", "")[:280] or f"From r/{post.get('subreddit', 'unknown')}"

        detected_type = detect_format(url, title, snippet)
        if resource_type in {"video", "blog"} and detected_type != resource_type:
            continue

        resources.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": "reddit",
            "format": detected_type,
            "domain": f"reddit.com/r/{post.get('subreddit', 'unknown')}",
            "upvotes": post.get("score", 0),
        })

    return resources[:limit]


def merge_and_rank(resources: List[Dict], limit: int) -> List[Dict]:
    unique: Dict[str, Dict] = {}

    for resource in resources:
        key = normalize_url(resource.get("url", ""))
        if not key:
            continue

        if key not in unique:
            unique[key] = resource
        else:
            if unique[key].get("source") == "reddit" and resource.get("source") == "google":
                unique[key] = resource

    merged = list(unique.values())
    for item in merged:
        item["score"] = score_resource(item)

    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    return merged[:limit]


def ask_gemini(message: str, topic: str, resources: List[Dict]) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key missing")

    context_lines = []
    for idx, res in enumerate(resources[:8], start=1):
        context_lines.append(
            f"{idx}. {res.get('title')} ({res.get('format')}) - {res.get('url')}"
        )

    context_text = "\n".join(context_lines) if context_lines else "No resources yet."

    system_prompt = (
        "You are a helpful study coach. Recommend practical learning paths and "
        "prioritize high-quality free resources. Keep answers concise, actionable, "
        "and supportive for frustrated students."
    )

    user_prompt = (
        f"Topic: {topic or 'General'}\n"
        f"Resources found:\n{context_text}\n\n"
        f"Student question: {message}\n\n"
        "Answer with:\n"
        "1) Best next 3 resources\n"
        "2) 7-day mini study plan\n"
        "3) Common mistakes to avoid"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt + "\n\n" + user_prompt}
                ]
            }
        ]
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return "I could not generate a response right now."

    parts = candidates[0].get("content", {}).get("parts", [])
    text_chunks = [p.get("text", "") for p in parts if p.get("text")]
    return "\n".join(text_chunks).strip() or "I could not generate a response right now."


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/search")
def api_search():
    topic = request.args.get("q", "").strip()
    resource_type = request.args.get("type", "all").strip().lower()
    limit = min(max(int(request.args.get("limit", 12)), 1), 20)

    if not topic:
        return jsonify({"error": "Query parameter 'q' is required."}), 400

    if resource_type not in {"all", "video", "blog"}:
        return jsonify({"error": "Type must be one of: all, video, blog."}), 400

    google_results = search_google(topic, resource_type, limit)
    reddit_results = search_reddit(topic, resource_type, limit)

    if resource_type == "all":
        combined = merge_and_rank(google_results + reddit_results, limit)
    else:
        combined = merge_and_rank(google_results + reddit_results, limit)

    return jsonify({
        "topic": topic,
        "type": resource_type,
        "count": len(combined),
        "resources": combined,
        "meta": {
            "google_configured": bool(GOOGLE_API_KEY and GOOGLE_CSE_ID),
            "gemini_configured": bool(GEMINI_API_KEY),
        }
    })


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    topic = (payload.get("topic") or "").strip()
    resources = payload.get("resources") or []

    if not message:
        return jsonify({"error": "Message is required."}), 400

    try:
        reply = ask_gemini(message, topic, resources)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except requests.RequestException:
        return jsonify({"error": "Failed to reach Gemini API."}), 502

    return jsonify({"reply": reply})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
