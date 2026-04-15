const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const backendLabel = document.getElementById("backend-label");

let backendUrl = "http://localhost:8001";
let backendName = "LangChain";

async function loadConfig() {
  try {
    const response = await fetch("/config.json");
    const config = await response.json();
    backendUrl = config.BACKEND_URL || backendUrl;
    backendName = backendUrl.includes("8002") ? "LlamaIndex" : "LangChain";
    backendLabel.textContent = `Backend: ${backendName} (${backendUrl})`;
  } catch (err) {
    backendLabel.textContent = "Backend config unavailable";
    console.error("Failed to load config", err);
  }
}

function appendMessage(role, text, options = {}) {
  const message = document.createElement("div");
  message.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  message.appendChild(bubble);

  if (role === "assistant" && options.traceId) {
    const meta = document.createElement("div");
    meta.className = "assistant-meta";

    const traceLink = document.createElement("button");
    traceLink.textContent = "View trace";
    traceLink.className = "feedback-button";
    traceLink.type = "button";
    traceLink.onclick = () => {
      navigator.clipboard.writeText(options.traceId).then(() => {
        traceLink.textContent = "Trace copied";
        setTimeout(() => {
          traceLink.textContent = "View trace";
        }, 1500);
      });
    };

    const feedbackRow = document.createElement("span");
    feedbackRow.className = "button-row";

    const thumbsUp = document.createElement("button");
    thumbsUp.className = "feedback-button";
    thumbsUp.type = "button";
    thumbsUp.textContent = "👍";
    thumbsUp.onclick = () => sendFeedback(options.traceId, "up", "Helpful answer");

    const thumbsDown = document.createElement("button");
    thumbsDown.className = "feedback-button";
    thumbsDown.type = "button";
    thumbsDown.textContent = "👎";
    thumbsDown.onclick = () => sendFeedback(options.traceId, "down", "Needs improvement");

    feedbackRow.appendChild(thumbsUp);
    feedbackRow.appendChild(thumbsDown);
    meta.appendChild(traceLink);
    meta.appendChild(feedbackRow);
    message.appendChild(meta);
  }

  if (options.status) {
    const status = document.createElement("div");
    status.className = "status";
    status.textContent = options.status;
    message.appendChild(status);
  }

  chatWindow.appendChild(message);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendFeedback(traceId, rating, comment) {
  try {
    const response = await fetch(`${backendUrl}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trace_id: traceId, rating, comment }),
    });
    const result = await response.json();
    if (response.ok) {
      appendMessage("assistant", `Feedback ${rating} recorded.`, { status: "Feedback sent." });
    } else {
      appendMessage("assistant", `Feedback failed: ${result.detail || result.error}`);
    }
  } catch (err) {
    appendMessage("assistant", "Feedback request failed.");
    console.error(err);
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    return;
  }

  appendMessage("user", question);
  questionInput.value = "";
  questionInput.disabled = true;

  try {
    const response = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const result = await response.json();
    if (response.ok) {
      appendMessage("assistant", result.answer || "No answer returned.", { traceId: result.trace_id });
    } else {
      appendMessage("assistant", result.detail || result.error || "Chat request failed.");
    }
  } catch (err) {
    appendMessage("assistant", "Chat request failed to reach backend.");
    console.error(err);
  } finally {
    questionInput.disabled = false;
    questionInput.focus();
  }
});

loadConfig();
