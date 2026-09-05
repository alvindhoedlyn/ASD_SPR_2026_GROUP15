// Static populated dataset
let journeys = [
    { journey_id: 1, label: "Sydney Weekend", locations: ["Bondi Beach", "Opera House", "Blue Mountains", "Harbour Bridge"] },
    { journey_id: 2, label: "Melbourne Foodie Trip", locations: ["Queen Victoria Market", "St Kilda", "Yarra Valley"] },
    { journey_id: 3, label: "Tropical North Queensland", locations: ["Great Barrier Reef", "Daintree Rainforest", "Cape Tribulation", "Kuranda"] },
    { journey_id: 4, label: "Red Centre Adventure", locations: ["Uluru", "Kata Tjuta", "Kings Canyon", "Alice Springs"] },
    { journey_id: 5, label: "Tasmanian Wilderness", locations: ["Cradle Mountain", "Freycinet National Park", "Mona Museum", "Port Arthur"] },
    { journey_id: 6, label: "Perth & Rottnest Island", locations: ["Kings Park", "Cottesloe Beach", "Rottnest Island", "Fremantle Markets"] },
    { journey_id: 7, label: "Barossa Wine & Culture", locations: ["Tanunda", "Barossa Valley Vineyards", "Adelaide Central Market", "Hahndorf"] },
    { journey_id: 8, label: "Great Ocean Road", locations: ["Twelve Apostles", "Lorne", "Bells Beach", "Loch Ard Gorge"] },
    { journey_id: 9, label: "Darwin & Top End", locations: ["Kakadu National Park", "Litchfield National Park", "Mindil Beach", "Katherine Gorge"] },
    { journey_id: 10, label: " Ningaloo Reef Explorer", locations: ["Exmouth", "Coral Bay", "Cape Range National Park", "Turquoise Bay"] }
];

const SAMPLE_DAY_POOL = [
    {
        summary: "Beach & sunset", location: "Bondi",
        activities: [
            { text: "Watch the Sunset!", icon: "🌅" },
            { text: "Take a Surf! High Waves", icon: "🏄" },
            { text: "Don't forget sunscreen!", icon: "🧴" }
        ]
    },
    {
        summary: "City & culture", location: "Sydney CBD",
        activities: [
            { text: "Visit Loc A", icon: "🏛️" },
            { text: "Visit Loc B", icon: "🖼️" },
            { text: "Visit Loc C", icon: "🍜" }
        ]
    },
    {
        summary: "Nature day", location: "Blue Mountains",
        activities: [
            { text: "Visit Loc A", icon: "🥾" },
            { text: "Visit Loc B", icon: "🌲" },
            { text: "Visit Loc C", icon: "📸" }
        ]
    },
    {
        summary: "Relax & depart", location: "Harbour",
        activities: [
            { text: "Visit Loc A", icon: "☕" },
            { text: "Visit Loc B", icon: "🛍️" },
            { text: "Visit Loc C", icon: "✈️" }
        ]
    },
];

let trips = [];
let nextTripId = 1;
let currentTripIndex = 0;
let activeDay = null;

// =====================================================================
// API INTEGRATION FUNCTIONS
// =====================================================================

async function mockGenerateDay(tripId, dayNumber) {
    const res = await fetch(`/api/trips/${tripId}/days/${dayNumber}`, { method: "PUT" });
    if (!res.ok) throw new Error("Failed to regenerate day");
    return await res.json();
}

async function mockGenerateTrip(journeyId, duration, preferences = "") {
    const res = await fetch("/api/trips/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ journeyId, duration, preferences })
    });
    if (!res.ok) throw new Error("Failed to generate trip");
    return await res.json();
}

// =====================================================================
// ELEMENT REFERENCES
// =====================================================================

const planFrame = document.getElementById("planFrame");
const emptyTripState = document.getElementById("emptyTripState");
const dayRow = document.getElementById("dayRow");
const noJourneyState = document.getElementById("noJourneyState");
const generateFormState = document.getElementById("generateFormState");

const generateNewTripBtn = document.getElementById("generateNewTripBtn");
const regenerateTripBtn = document.getElementById("regenerateTripBtn");
const deleteTripBtn = document.getElementById("deleteTripBtn");

const tripNavLabel = document.getElementById("tripNavLabel");
const prevTripBtn = document.getElementById("prevTripBtn");
const nextTripBtn = document.getElementById("nextTripBtn");

const journeySelect = document.getElementById("journeySelect");
const dayCountInput = document.getElementById("dayCountInput");
const preferencesInput = document.getElementById("preferencesInput");
const generateConfirmBtn = document.getElementById("generateConfirmBtn");

const dayOverlay = document.getElementById("dayOverlay");
const dayModalTitle = document.getElementById("dayModalTitle");
const activityGrid = document.getElementById("activityGrid");
const regenerateDayBtn = document.getElementById("regenerateDayBtn");
const deleteDayBtn = document.getElementById("deleteDayBtn");

// =====================================================================
// RENDERING & STATE MACHINE
// =====================================================================

function showFrameState(activeId) {
    [emptyTripState, dayRow, noJourneyState, generateFormState].forEach(el => {
        if (el) el.hidden = (el.id !== activeId);
    });
}

function renderTripNav() {
    if (trips.length === 0) {
        tripNavLabel.textContent = "No trips";
        prevTripBtn.disabled = true;
        nextTripBtn.disabled = true;
        return;
    }
    tripNavLabel.textContent = `TRIP ${currentTripIndex + 1}`;
    prevTripBtn.disabled = currentTripIndex === 0;
    nextTripBtn.disabled = currentTripIndex === trips.length - 1;
}

function renderCurrentTrip() {
    if (trips.length === 0) {
        showFrameState("emptyTripState");
        regenerateTripBtn.disabled = true;
        deleteTripBtn.disabled = true;
        renderTripNav();
        return;
    }

    const trip = trips[currentTripIndex];
    renderDays(trip);
    showFrameState("dayRow");
    regenerateTripBtn.disabled = false;
    deleteTripBtn.disabled = false;
    renderTripNav();
}

function renderDays(trip) {
    dayRow.innerHTML = "";
    (trip.days || []).forEach(day => {
        const card = document.createElement("div");
        card.className = "day-card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        card.setAttribute("aria-label", `Open Day ${day.day_number} details`);

        const activitiesHtml = (day.activities || []).map(a => `<li>${a.text}</li>`).join("");
        card.innerHTML = `
        <h2>DAY ${day.day_number}</h2>
        <div class="summary">${day.summary || ''}</div>
        <ul>${activitiesHtml}</ul>
      `;

        card.addEventListener("click", () => openDayModal(day));
        card.addEventListener("keydown", e => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDayModal(day); }
        });

        dayRow.appendChild(card);
    });
}

function populateJourneySelect() {
    journeySelect.innerHTML = journeys
        .map(j => `<option value="${j.journey_id}">${j.label}</option>`)
        .join("");
}

// =====================================================================
// INITIALIZATION
// =====================================================================

async function initApp() {
    try {
        // Try fetching journeys from database; fallback to hardcoded list if fetch fails
        const jRes = await fetch("/api/journeys");
        if (jRes.ok) {
            const apiJourneys = await jRes.json();
            if (apiJourneys.length > 0) journeys = apiJourneys;
        }
    } catch (err) {
        console.warn("Could not fetch remote journeys, using fallback preset data.", err);
    }

    try {
        const tRes = await fetch("/api/trips");
        if (tRes.ok) {
            trips = await tRes.json();
            currentTripIndex = trips.length > 0 ? trips.length - 1 : 0;
        }
    } catch (err) {
        console.error("Initialization failed:", err);
    } finally {
        renderCurrentTrip();
    }
}

// =====================================================================
// UI LISTENERS
// =====================================================================

generateNewTripBtn.addEventListener("click", () => {
    if (journeys.length === 0) {
        showFrameState("noJourneyState");
    } else {
        populateJourneySelect();
        showFrameState("generateFormState");
    }
});

generateConfirmBtn.addEventListener("click", async () => {
    const duration = parseInt(dayCountInput.value, 10);
    const journeyId = parseInt(journeySelect.value, 10);
    const preferences = preferencesInput.value.trim();

    if (!duration || duration < 1) {
        alert("Enter a valid number of days.");
        return;
    }

    try {
        const newTrip = await mockGenerateTrip(journeyId, duration, preferences);
        trips.push(newTrip);
        currentTripIndex = trips.length - 1;
        renderCurrentTrip();
    } catch (err) {
        alert(err.message);
    }
});

regenerateTripBtn.addEventListener("click", async () => {
    if (trips.length === 0) return;
    const trip = trips[currentTripIndex];

    try {
        const res = await fetch(`/api/trips/${trip.trip_id}/regenerate`, { method: "PUT" });
        if (!res.ok) throw new Error("Failed to regenerate trip");

        const data = await res.json();
        trip.days = data.days;
        renderCurrentTrip();
    } catch (err) {
        alert(err.message);
    }
});

deleteTripBtn.addEventListener("click", async () => {
    if (trips.length === 0) return;
    if (!confirm("Delete this trip? This can't be undone.")) return;

    const currentTrip = trips[currentTripIndex];

    try {
        const response = await fetch(`/api/trips/${currentTrip.trip_id}`, { method: "DELETE" });
        if (!response.ok) throw new Error("Failed to delete trip");

        trips.splice(currentTripIndex, 1);
        currentTripIndex = Math.max(0, Math.min(currentTripIndex, trips.length - 1));
        renderCurrentTrip();
    } catch (err) {
        alert(err.message);
    }
});

prevTripBtn.addEventListener("click", () => {
    if (currentTripIndex > 0) {
        currentTripIndex--;
        renderCurrentTrip();
    }
});

nextTripBtn.addEventListener("click", () => {
    if (currentTripIndex < trips.length - 1) {
        currentTripIndex++;
        renderCurrentTrip();
    }
});

// =====================================================================
// DAY DETAIL MODAL
// =====================================================================

function openDayModal(day) {
    activeDay = day;
    dayModalTitle.textContent = `Day ${String(day.day_number).padStart(2, "0")} — ${day.location || 'Location'}`;
    activityGrid.innerHTML = (day.activities || []).map(a => `
      <div class="activity-card">
        <figure>
          <div class="activity-photo">${a.icon || '📍'}</div>
          <figcaption>${a.text}</figcaption>
        </figure>
      </div>
    `).join("");
    dayOverlay.classList.add("open");
}

document.getElementById("closeDayModal").addEventListener("click", () => {
    dayOverlay.classList.remove("open");
});

dayOverlay.addEventListener("click", e => {
    if (e.target === dayOverlay) dayOverlay.classList.remove("open");
});

regenerateDayBtn.addEventListener("click", async () => {
    if (!activeDay || trips.length === 0) return;
    const trip = trips[currentTripIndex];

    try {
        const updatedDay = await mockGenerateDay(trip.trip_id, activeDay.day_number);
        const idx = trip.days.findIndex(d => d.day_number === activeDay.day_number);

        trip.days[idx] = updatedDay;
        activeDay = trip.days[idx];

        openDayModal(activeDay);
        renderDays(trip);
    } catch (err) {
        alert(err.message);
    }
});

deleteDayBtn.addEventListener("click", async () => {
    if (!activeDay || trips.length === 0) return;
    const trip = trips[currentTripIndex];

    try {
        const response = await fetch(`/api/trips/${trip.trip_id}/days/${activeDay.day_number}`, {
            method: "DELETE"
        });

        if (!response.ok) throw new Error("Failed to delete day");

        trip.days = trip.days
            .filter(d => d.day_number !== activeDay.day_number)
            .map((d, i) => ({ ...d, day_number: i + 1 }));

        dayOverlay.classList.remove("open");
        renderDays(trip);
    } catch (err) {
        alert(err.message);
    }
});

// =====================================================================
// CHAT PANEL
// =====================================================================

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
if (openChatBtn) openChatBtn.addEventListener("click", () => toggleChat(true));
if (closeChatBtn) closeChatBtn.addEventListener("click", () => toggleChat(false));

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

    addBubble("assistant", "…thinking…");
    const placeholder = chatBody.lastElementChild;
    try {
        const formData = new FormData();
        formData.append("question", text);
        formData.append("itinerary", JSON.stringify(trips[currentTripIndex] || {}));

        const res = await fetch("/ask-with-context", {
            method: "POST",
            body: formData
        });

        const data = await res.text();
        placeholder.innerHTML = data;
    } catch (err) {
        placeholder.textContent = "Sorry, something went wrong reaching Buddy.";
    }
}

if (sendChatBtn) sendChatBtn.addEventListener("click", sendMessage);
if (chatInput) chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });

initApp();