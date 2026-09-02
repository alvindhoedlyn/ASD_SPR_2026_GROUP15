// ---- Sample data shaped like what /api/generate-plan would return ----
// Swap this for a fetch() call to your Flask backend.
const itinerary = {
    days: [
        {
            day_number: 1,
            summary: "Beach & sunset",
            location: "Bondi",
            activities: [
                { text: "Watch the Sunset!", icon: "🌅" },
                { text: "Take a Surf! High Waves", icon: "🏄" },
                { text: "Don't forget sunscreen!", icon: "🧴" }
            ]
        },
        {
            day_number: 2, summary: "City & culture", location: "Sydney CBD",
            activities: [
                { text: "Visit Loc A", icon: "🏛️" },
                { text: "Visit Loc B", icon: "🖼️" },
                { text: "Visit Loc C", icon: "🍜" }
            ]
        },
        {
            day_number: 3, summary: "Nature day", location: "Blue Mountains",
            activities: [
                { text: "Visit Loc A", icon: "🥾" },
                { text: "Visit Loc B", icon: "🌲" },
                { text: "Visit Loc C", icon: "📸" }
            ]
        },
        {
            day_number: 4, summary: "Relax & depart", location: "Harbour",
            activities: [
                { text: "Visit Loc A", icon: "☕" },
                { text: "Visit Loc B", icon: "🛍️" },
                { text: "Visit Loc C", icon: "✈️" }
            ]
        },
        {
            day_number: 5, summary: "Relax & depart", location: "Harbour",
            activities: [
                { text: "Visit Loc A", icon: "☕" },
                { text: "Visit Loc B", icon: "🛍️" },
                { text: "Visit Loc C", icon: "✈️" }
            ]
        },
        {
            day_number: 6, summary: "Relax & depart", location: "Harbour",
            activities: [
                { text: "Visit Loc A", icon: "☕" },
                { text: "Visit Loc B", icon: "🛍️" },
                { text: "Visit Loc C", icon: "✈️" }
            ]
        }
    ]
};

const dayRow = document.getElementById("dayRow");
const dayOverlay = document.getElementById("dayOverlay");
const dayModalTitle = document.getElementById("dayModalTitle");
const activityGrid = document.getElementById("activityGrid");
const rewriteDayBtn = document.getElementById("rewriteDayBtn");
let activeDay = null;

function renderDays() {
    dayRow.innerHTML = "";
    itinerary.days.forEach(day => {
        const card = document.createElement("div");
        card.className = "day-card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        card.setAttribute("aria-label", `Open Day ${day.day_number} details`);

        const activitiesHtml = day.activities
            .map(a => `<li>${a.text}</li>`)
            .join("");

        card.innerHTML = `
        <h2>DAY ${day.day_number}</h2>
        <div class="summary">${day.summary}</div>
        <ul>${activitiesHtml}</ul>
      `;

        card.addEventListener("click", () => openDayModal(day));
        card.addEventListener("keydown", e => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDayModal(day); }
        });

        dayRow.appendChild(card);
    });
}

function openDayModal(day) {
    activeDay = day;
    dayModalTitle.textContent = `Day ${String(day.day_number).padStart(2, "0")} — ${day.location}`;
    activityGrid.innerHTML = day.activities.map(a => `
      <div class="activity-card">
        <figure>
          <div class="activity-photo">${a.icon}</div>
          <figcaption>${a.text}</figcaption>
        </figure>
      </div>
    `).join("");
    dayOverlay.classList.add("open");
    rewriteDayBtn.removeAttribute("disabled");
}

document.getElementById("closeDayModal").addEventListener("click", () => {
    dayOverlay.classList.remove("open");
});
dayOverlay.addEventListener("click", e => {
    if (e.target === dayOverlay) dayOverlay.classList.remove("open");
});

// ---- Chat panel ----
const chatPanel = document.getElementById("chatPanel");
const openChatBtn = document.getElementById("openChatBtn");
const closeChatBtn = document.getElementById("closeChatBtn");
const chatBody = document.getElementById("chatBody");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");

function toggleChat(open) {
    chatPanel.classList.toggle("open", open);
    chatPanel.setAttribute("aria-hidden", String(!open));
}
openChatBtn.addEventListener("click", () => toggleChat(true));
closeChatBtn.addEventListener("click", () => toggleChat(false));

function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = text;
    chatBody.appendChild(div);
    chatBody.scrollTop = chatBody.scrollHeight;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    addBubble("user", text);
    chatInput.value = "";

    // Replace this block with a real fetch("/api/chat", {...}) call to Flask/Ollama
    addBubble("assistant", "…thinking…");
    const placeholder = chatBody.lastElementChild;
    try {
        // Example of the real call:
        // const res = await fetch("/api/chat", {
        //   method: "POST",
        //   headers: {"Content-Type": "application/json"},
        //   body: JSON.stringify({ message: text, history: [] })
        // });
        // const data = await res.json();
        // placeholder.textContent = data.reply;
        placeholder.textContent = "This is a placeholder reply — wire this panel up to /api/chat.";
    } catch (err) {
        placeholder.textContent = "Sorry, something went wrong reaching Buddy.";
    }
}

sendChatBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });

// ---- Buttons (wire these to your Flask routes) ----
document.getElementById("generatePlanBtn").addEventListener("click", () => {
    // fetch("/api/generate-plan", { method: "POST", ... }).then(...).then(renderDays)
    renderDays();
});
document.getElementById("addLocationBtn").addEventListener("click", () => {
    alert("Hook this up to your add-location form/modal.");
});
document.getElementById("rewriteDayBtn").addEventListener("click", () => {
    if (!activeDay) return;
    alert(`Hook this up to POST /api/rewrite-day for Day ${activeDay.day_number}.`);
});

renderDays();