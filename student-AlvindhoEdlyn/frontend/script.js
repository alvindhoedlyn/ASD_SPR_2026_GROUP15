// =====================================================================
// SAMPLE DATA — shaped like what the backend will eventually return.
// Swap the functions marked "MOCK" for real fetch() calls once the
// Flask routes are wired up; everything else (state machine, rendering)
// stays the same.
// =====================================================================

// A journey = a saved set of locations (from the Locations page).
// Set this to [] to preview the "No Journey Found" state (Page 2).
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

// A pool of sample day content, cycled through by the mock generator below.
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

// Trips the user has generated. TEST DATA is pre-populated below so the app
// opens straight into the day-card view (dayRow), bypassing "Generate New
// Trip" entirely — use this to test day cards, the day-detail modal,
// Re-generate/Delete, and the trip navigator without needing the generate
// flow to work first.
//
// To go back to testing the empty/generate flow from scratch, change this
// back to: let trips = [];
let trips = [
    {
        trip_id: 1,
        journey_id: 1,
        duration: 4,
        days: SAMPLE_DAY_POOL.map((sample, i) => ({ day_number: i + 1, ...sample })),
    },
    {
        trip_id: 2,
        journey_id: 2,
        duration: 2,
        days: [
            {
                summary: "Market crawl", location: "Melbourne CBD", day_number: 1,
                activities: [
                    { text: "Queen Vic Market", icon: "🧺" },
                    { text: "Laneway coffee", icon: "☕" },
                    { text: "Rooftop bar", icon: "🍹" }
                ]
            },
            {
                summary: "Wine day", location: "Yarra Valley", day_number: 2,
                activities: [
                    { text: "Winery tour", icon: "🍇" },
                    { text: "Cheese tasting", icon: "🧀" },
                    { text: "Sunset drive back", icon: "🚗" }
                ]
            },
        ],
    },
];
let nextTripId = 3; // continue after the two test trips above

// Index into `trips` for the trip currently on screen. Starts on the latest
// test trip, matching the "default = latest trip" spec.
let currentTripIndex = trips.length - 1;
let activeDay = null; // the day currently open in the day-detail modal


// =====================================================================
// MOCK GENERATORS — replace these two with real API calls.
// =====================================================================

function mockGenerateDay(dayNumber, journeyId) {
    // Replace with the real call, e.g.:
    // const res = await fetch(`/api/trips/${tripId}/days`, { method: "POST", ... });
    const sample = SAMPLE_DAY_POOL[(dayNumber - 1) % SAMPLE_DAY_POOL.length];
    return { day_number: dayNumber, ...sample };
}

function mockGenerateTrip(journeyId, duration) {
    // Replace with the real call, e.g.:
    // const res = await fetch("/api/trips", {
    //   method: "POST",
    //   headers: {"Content-Type": "application/json"},
    //   body: JSON.stringify({ journey_id: journeyId, duration, preferences })
    // });
    // const trip = await res.json();
    const days = Array.from({ length: duration }, (_, i) => mockGenerateDay(i + 1, journeyId));
    return { trip_id: nextTripId++, journey_id: journeyId, duration, days };
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
// PLAN-FRAME STATE MACHINE
// Exactly one of these four is visible at a time:
//   emptyTripState   — Page 1: Trip table empty
//   dayRow           — a trip is loaded, showing its day cards
//   noJourneyState   — Page 2: "Generate New Trip" clicked, Journey table empty
//   generateFormState — Page 3: "Generate New Trip" clicked, journeys exist
// =====================================================================

function showFrameState(activeId) {
    [emptyTripState, dayRow, noJourneyState, generateFormState].forEach(el => {
        el.hidden = (el.id !== activeId);
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
    trip.days.forEach(day => {
        const card = document.createElement("div");
        card.className = "day-card";
        card.tabIndex = 0;
        card.setAttribute("role", "button");
        card.setAttribute("aria-label", `Open Day ${day.day_number} details`);

        const activitiesHtml = day.activities.map(a => `<li>${a.text}</li>`).join("");
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


// =====================================================================
// GENERATE NEW TRIP FLOW (Pages 2 & 3)
// =====================================================================

function populateJourneySelect() {
    journeySelect.innerHTML = journeys
        .map(j => `<option value="${j.journey_id}">${j.label}</option>`)
        .join("");
}

generateNewTripBtn.addEventListener("click", () => {
    if (journeys.length === 0) {
        showFrameState("noJourneyState");
    } else {
        populateJourneySelect();
        showFrameState("generateFormState");
    }
});

generateConfirmBtn.addEventListener("click", () => {
    const duration = parseInt(dayCountInput.value, 10);
    const journeyId = parseInt(journeySelect.value, 10);
    const preferences = preferencesInput.value.trim(); // include this in the real POST body

    if (!duration || duration < 1) {
        alert("Enter a valid number of days.");
        return;
    }

    const newTrip = mockGenerateTrip(journeyId, duration, preferences);
    trips.push(newTrip);
    currentTripIndex = trips.length - 1; // newest trip becomes "current"
    renderCurrentTrip();
});


// =====================================================================
// MAIN ACTION BUTTONS
// =====================================================================

regenerateTripBtn.addEventListener("click", () => {
    if (trips.length === 0) return;
    const trip = trips[currentTripIndex];
    // Replace with: fetch(`/api/trips/${trip.trip_id}/regenerate`, { method: "PUT" })
    trip.days = trip.days.map((_, i) => mockGenerateDay(i + 1, trip.journey_id));
    renderCurrentTrip();
});

deleteTripBtn.addEventListener("click", () => {
    if (trips.length === 0) return;
    if (!confirm("Delete this trip? This can't be undone.")) return;
    // Replace with: fetch(`/api/trips/${trips[currentTripIndex].trip_id}`, { method: "DELETE" })
    trips.splice(currentTripIndex, 1);
    currentTripIndex = Math.min(currentTripIndex, trips.length - 1);
    renderCurrentTrip();
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
}

document.getElementById("closeDayModal").addEventListener("click", () => {
    dayOverlay.classList.remove("open");
});
dayOverlay.addEventListener("click", e => {
    if (e.target === dayOverlay) dayOverlay.classList.remove("open");
});

regenerateDayBtn.addEventListener("click", () => {
    if (!activeDay || trips.length === 0) return;
    const trip = trips[currentTripIndex];
    // Replace with: fetch(`/api/trips/${trip.trip_id}/days/${activeDay.day_number}`, { method: "PUT" })
    const idx = trip.days.findIndex(d => d.day_number === activeDay.day_number);
    trip.days[idx] = mockGenerateDay(activeDay.day_number, trip.journey_id);
    activeDay = trip.days[idx];
    openDayModal(activeDay);
    renderDays(trip);
});

deleteDayBtn.addEventListener("click", () => {
    if (!activeDay || trips.length === 0) return;
    if (!confirm(`Delete Day ${activeDay.day_number}?`)) return;
    const trip = trips[currentTripIndex];
    // Replace with: fetch(`/api/trips/${trip.trip_id}/days/${activeDay.day_number}`, { method: "DELETE" })
    trip.days = trip.days
        .filter(d => d.day_number !== activeDay.day_number)
        .map((d, i) => ({ ...d, day_number: i + 1 })); // client-side renumber for display only
    dayOverlay.classList.remove("open");
    renderDays(trip);
});


// =====================================================================
// CHAT PANEL — Buddy also answers general FAQ / packing / itinerary
// questions per the workflow spec; behavior unchanged from before.
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

    addBubble("assistant", "…thinking…");
    const placeholder = chatBody.lastElementChild;
    try {
        const formData = new FormData();
        formData.append("question", text);

        const res = await fetch("http://localhost:5001/ask-with-context", {
            method: "POST",
            body: formData
        });

        const data = await res.text();
        placeholder.innerHTML = data;
    } catch (err) {
        placeholder.textContent = "Sorry, something went wrong reaching Buddy.";
    }
}

sendChatBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendMessage(); });


// =====================================================================
// INIT
// =====================================================================

renderCurrentTrip();
