const searchForm = document.getElementById("search-form");
const topicInput = document.getElementById("topic");
const resourceTypeInput = document.getElementById("resource-type");
const resultsContainer = document.getElementById("results");
const resultMeta = document.getElementById("result-meta");
const resourceTemplate = document.getElementById("resource-template");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatLog = document.getElementById("chat-log");

let latestResources = [];
let latestTopic = "";

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = escapeHtml(text);
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderResults(resources) {
  resultsContainer.innerHTML = "";

  if (!resources.length) {
    resultsContainer.innerHTML = '<div class="empty">No matching resources found. Try another topic or format.</div>';
    return;
  }

  resources.forEach((resource, index) => {
    const fragment = resourceTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".card");

    card.style.animationDelay = `${index * 40}ms`;
    fragment.querySelector(".source").textContent = resource.source || "unknown";
    fragment.querySelector(".format").textContent = resource.format || "article";
    fragment.querySelector(".score").textContent = `score ${resource.score ?? 0}`;
    fragment.querySelector(".title").textContent = resource.title || "Untitled";
    fragment.querySelector(".snippet").textContent = resource.snippet || "No description provided.";
    fragment.querySelector(".domain").textContent = resource.domain || "web";

    const visit = fragment.querySelector(".visit");
    visit.href = resource.url;

    resultsContainer.appendChild(fragment);
  });
}

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const topic = topicInput.value.trim();
  const type = resourceTypeInput.value;
  if (!topic) {
    return;
  }

  resultMeta.textContent = "Searching Google + Reddit...";

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(topic)}&type=${encodeURIComponent(type)}&limit=12`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Search failed");
    }

    latestResources = data.resources || [];
    latestTopic = topic;

    renderResults(latestResources);
    resultMeta.textContent = `Found ${data.count} ranked resources for "${topic}" (${type}).`;
  } catch (error) {
    renderResults([]);
    resultMeta.textContent = error.message;
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = chatInput.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  chatInput.value = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        topic: latestTopic,
        resources: latestResources,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "AI request failed");
    }

    appendMessage("ai", data.reply || "No response from AI.");
  } catch (error) {
    appendMessage("ai", `Error: ${error.message}`);
  }
});
