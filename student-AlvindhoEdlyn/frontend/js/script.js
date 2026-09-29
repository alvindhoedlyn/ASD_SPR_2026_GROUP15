document.addEventListener("DOMContentLoaded", () => {
  // State management
  let trips = [];
  let currentTripIndex = 0;
  let activeDayNumber = null;
  let availableJourneys = [];

  // DOM Elements - Plan Frame
  const emptyTripState = document.getElementById("emptyTripState");
  const dayRow = document.getElementById("dayRow");
  const noJourneyState = document.getElementById("noJourneyState");
  const generateFormState = document.getElementById("generateFormState");

  // DOM Elements - Form
  const dayCountInput = document.getElementById("dayCountInput");
  const journeySelect = document.getElementById("journeySelect");
  const preferencesInput = document.getElementById("preferencesInput");
  const generateConfirmBtn = document.getElementById("generateConfirmBtn");

  // DOM Elements - Global Action Buttons
  const generateNewTripBtn = document.getElementById("generateNewTripBtn");
  const regenerateTripBtn = document.getElementById("regenerateTripBtn");
  const deleteTripBtn = document.getElementById("deleteTripBtn");

  // DOM Elements - Trip Navigation
  const prevTripBtn = document.getElementById("prevTripBtn");
  const nextTripBtn = document.getElementById("nextTripBtn");
  const tripNavLabel = document.getElementById("tripNavLabel");

  // DOM Elements - Day Modal
  const dayOverlay = document.getElementById("dayOverlay");
  const closeDayModal = document.getElementById("closeDayModal");
  const dayModalTitle = document.getElementById("dayModalTitle");
  const activityGrid = document.getElementById("activityGrid");
  const regenerateDayBtn = document.getElementById("regenerateDayBtn");
  const deleteDayBtn = document.getElementById("deleteDayBtn");

  // DOM Elements - Chat Panel
  const openChatBtn = document.getElementById("openChatBtn");
  const closeChatBtn = document.getElementById("closeChatBtn");
  const chatPanel = document.getElementById("chatPanel");
  const chatBody = document.getElementById("chatBody");
  const chatInput = document.getElementById("chatInput");
  const sendChatBtn = document.getElementById("sendChatBtn");

  // Initial Load
  init();

  async function init() {
    updateHeaderUserInfo();
    await fetchJourneys();
    await fetchTrips();
    setupEventListeners();
  }

  // -------------------------------------------------------------
  // Data Fetching Operations
  // -------------------------------------------------------------

  function updateHeaderUserInfo() {
    const userNameEl = document.getElementById("userName");
    const userIdEl = document.getElementById("userId");

    if (userNameEl && typeof getUsername === "function") {
      userNameEl.textContent = getUsername();
    }
    if (userIdEl && typeof getUserId === "function") {
      userIdEl.textContent = `#${getUserId()}`;
    }
  }

  async function fetchJourneys() {
    try {
      const res = await fetch("/api/journeys");
      if (!res.ok) throw new Error("Failed to load journeys");
      availableJourneys = await res.json();

      journeySelect.innerHTML = "";
      if (availableJourneys.length === 0) {
        journeySelect.innerHTML = "<option disabled>No journeys available</option>";
      } else {
        availableJourneys.forEach((j) => {
          const opt = document.createElement("option");
          opt.value = j.journey_id;
          opt.textContent = `${j.label} (${j.locations.length} locations)`;
          journeySelect.appendChild(opt);
        });
      }
    } catch (err) {
      console.error("Error fetching journeys:", err);
    }
  }

  async function fetchTrips() {
    try {
      const res = await fetch("/api/trips");
      if (!res.ok) throw new Error("Failed to load trips");
      trips = await res.json();

      if (trips.length > 0) {
        currentTripIndex = trips.length - 1; // Default to most recent
        renderCurrentTrip();
      } else {
        showFrameState(emptyTripState);
        updateNavigationUI();
      }
    } catch (err) {
      console.error("Error fetching trips:", err);
      showFrameState(emptyTripState);
    }
  }

  // -------------------------------------------------------------
  // Rendering & State Helpers
  // -------------------------------------------------------------

  function showFrameState(activeElement) {
    [emptyTripState, dayRow, noJourneyState, generateFormState].forEach((el) => {
      el.hidden = el !== activeElement;
    });
  }

  function renderCurrentTrip() {
    if (trips.length === 0) {
      showFrameState(emptyTripState);
      updateNavigationUI();
      return;
    }

    const currentTrip = trips[currentTripIndex];
    showFrameState(dayRow);
    dayRow.innerHTML = "";

    if (!currentTrip.days || currentTrip.days.length === 0) {
      dayRow.innerHTML = "<p>This trip has no days remaining.</p>";
    } else {
      currentTrip.days.forEach((day) => {
        const card = document.createElement("div");
        card.className = "day-card";
        card.innerHTML = `
          <h3>Day ${String(day.day_number).padStart(2, "0")}</h3>
          <p class="day-location">${day.location}</p>
          <p class="day-summary">${day.summary || day.itinerary}</p>
        `;
        card.addEventListener("click", () => openDayDetails(day));
        dayRow.appendChild(card);
      });
    }

    updateNavigationUI();
  }

  function updateNavigationUI() {
    const hasTrips = trips.length > 0;
    regenerateTripBtn.disabled = !hasTrips;
    deleteTripBtn.disabled = !hasTrips;

    if (!hasTrips) {
      tripNavLabel.textContent = "No trips";
      prevTripBtn.disabled = true;
      nextTripBtn.disabled = true;
      return;
    }

    tripNavLabel.textContent = `Trip ${currentTripIndex + 1} of ${trips.length}`;
    prevTripBtn.disabled = currentTripIndex === 0;
    nextTripBtn.disabled = currentTripIndex === trips.length - 1;
  }

  // -------------------------------------------------------------
  // Action Handlers (API Calls)
  // -------------------------------------------------------------

  async function handleGenerateTrip() {
    const journeyId = parseInt(journeySelect.value, 10);
    const duration = parseInt(dayCountInput.value, 10);
    const preferences = preferencesInput.value.trim();
    const activeUserId = parseInt(localStorage.getItem("userId"), 10) || 1;

    if (!journeyId) {
      if (availableJourneys.length === 0) {
        showFrameState(noJourneyState);
      } else {
        alert("Please select a valid set of locations.");
      }
      return;
    }

    try {
      generateConfirmBtn.disabled = true;
      generateConfirmBtn.textContent = "Generating...";

      const res = await fetch("/api/trips/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          journeyId: journeyId,
          duration: duration,
          preferences: preferences,
          userId: activeUserId
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to generate trip");
      }

      await fetchTrips(); // Reload all trips and display latest
      preferencesInput.value = "";
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      generateConfirmBtn.disabled = false;
      generateConfirmBtn.textContent = "Generate!";
    }
  }

  async function handleDeleteTrip() {
    if (trips.length === 0) return;
    const tripId = trips[currentTripIndex].trip_id;

    if (!confirm("Are you sure you want to delete this trip?")) return;

    try {
      const res = await fetch(`/api/trips/${tripId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete trip");

      await fetchTrips();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }

  async function handleRegenerateTrip() {
    if (trips.length === 0 || currentTripIndex < 0) {
      console.error("No active trip found to regenerate.");
      return;
    }

    const currentTrip = trips[currentTripIndex];
    const tripId = currentTrip.trip_id;

    try {
      regenerateTripBtn.disabled = true;

      const response = await fetch(`/api/trips/${tripId}/regenerate`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to regenerate trip");
      }

      const updatedTrip = await response.json();

      // Update local trips array state and re-render view
      trips[currentTripIndex] = updatedTrip;
      renderCurrentTrip();

    } catch (error) {
      console.error("Error regenerating trip:", error);
      alert(`Could not regenerate trip: ${error.message}`);
    } finally {
      regenerateTripBtn.disabled = false;
    }
  }

  async function handleRegenerateDay() {
    if (trips.length === 0 || !activeDayNumber) return;
    const tripId = trips[currentTripIndex].trip_id;

    try {
      regenerateDayBtn.disabled = true;
      regenerateDayBtn.textContent = "Updating...";

      const res = await fetch(`/api/trips/${tripId}/days/${activeDayNumber}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" }
      });

      if (!res.ok) throw new Error("Failed to regenerate day");

      const updatedDay = await res.json();

      // Refresh current local trip data
      const dayIdx = trips[currentTripIndex].days.findIndex(
        (d) => d.day_number === activeDayNumber
      );
      if (dayIdx !== -1) {
        trips[currentTripIndex].days[dayIdx] = updatedDay;
      }

      openDayDetails(updatedDay);
      renderCurrentTrip();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      regenerateDayBtn.disabled = false;
      regenerateDayBtn.textContent = "Re-generate";
    }
  }

  async function handleDeleteDay() {
    if (trips.length === 0 || !activeDayNumber) return;
    const tripId = trips[currentTripIndex].trip_id;

    if (!confirm(`Are you sure you want to delete Day ${activeDayNumber}?`)) return;

    try {
      deleteDayBtn.disabled = true;

      const res = await fetch(`/api/trips/${tripId}/days/${activeDayNumber}`, {
        method: "DELETE"
      });

      if (!res.ok) throw new Error("Failed to delete day");

      closeDayModalUI();
      await fetchTrips();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      deleteDayBtn.disabled = false;
    }
  }

  // -------------------------------------------------------------
  // Day Details Modal
  // -------------------------------------------------------------

  function openDayDetails(day) {
    activeDayNumber = day.day_number;
    dayModalTitle.textContent = `Day ${String(day.day_number).padStart(2, "0")} — ${day.location}`;

    activityGrid.innerHTML = "";
    if (day.activities && day.activities.length > 0) {
      day.activities.forEach((act) => {
        const item = document.createElement("div");
        item.className = "activity-item";
        item.innerHTML = `<span class="icon">${act.icon || "📍"}</span> <span>${act.text}</span>`;
        activityGrid.appendChild(item);
      });
    } else {
      activityGrid.innerHTML = `<p>${day.summary || day.itinerary || "No activities specified."}</p>`;
    }

    dayOverlay.style.display = "flex";
  }

  function closeDayModalUI() {
    dayOverlay.style.display = "none";
    activeDayNumber = null;
  }

  // -------------------------------------------------------------
  // AI Assistant Chat Panel
  // -------------------------------------------------------------
async function handleSendChat() {
  const question = chatInput.value.trim();
  if (!question) return;

  appendChatBubble(question, "user");
  chatInput.value = "";

  // Safe itinerary context parsing with fallbacks
  let itineraryContext = "No active trip.";
  if (trips.length > 0 && trips[currentTripIndex]) {
    const trip = trips[currentTripIndex];
    if (trip.days && trip.days.length > 0) {
      itineraryContext = trip.days
        .map((d, idx) => {
          const dayNum = d.day_number || idx + 1;
          const location = d.location || "Scheduled Location";
          const details = d.summary || d.itinerary || d.activity || "";
          return `Day ${dayNum} (${location}): ${details}`;
        })
        .join("\n");
    }
  }

  const typingBubble = appendChatBubble("Thinking...", "assistant");

  try {
    const res = await fetch("/ask-with-context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        itinerary: itineraryContext
      })
    });

    const responseText = await res.text();

    if (!res.ok) {
      console.error(`Server Error (${res.status}):`, responseText);
      throw new Error(`Server returned status ${res.status}`);
    }

    // Safely render response HTML or plain text
    typingBubble.innerHTML = responseText;
  } catch (err) {
    console.error("Chat Request Failed:", err);
    typingBubble.textContent = "Sorry, I had trouble reaching the AI service. Check server logs.";
  }

  chatBody.scrollTop = chatBody.scrollHeight;
}

  function appendChatBubble(text, sender) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${sender}`;
    bubble.textContent = text;
    chatBody.appendChild(bubble);
    chatBody.scrollTop = chatBody.scrollHeight;
    return bubble;
  }

  // -------------------------------------------------------------
  // Event Listeners Setup
  // -------------------------------------------------------------

  function setupEventListeners() {
    // Generate Form Controls
    generateNewTripBtn.addEventListener("click", () => {
      if (availableJourneys.length === 0) {
        showFrameState(noJourneyState);
      } else {
        showFrameState(generateFormState);
      }
    });

    generateConfirmBtn.addEventListener("click", handleGenerateTrip);

    // Global Trip Controls
    deleteTripBtn.addEventListener("click", handleDeleteTrip);
    
    // Connected to full trip regeneration endpoint
    regenerateTripBtn.addEventListener("click", handleRegenerateTrip);

    // Navigation Controls
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

    // Modal Controls
    closeDayModal.addEventListener("click", closeDayModalUI);
    dayOverlay.addEventListener("click", (e) => {
      if (e.target === dayOverlay) closeDayModalUI();
    });
    regenerateDayBtn.addEventListener("click", handleRegenerateDay);
    deleteDayBtn.addEventListener("click", handleDeleteDay);

    // Chat Panel Controls
    openChatBtn.addEventListener("click", () => {
      chatPanel.setAttribute("aria-hidden", "false");
      chatPanel.classList.add("open");
    });

    closeChatBtn.addEventListener("click", () => {
      chatPanel.setAttribute("aria-hidden", "true");
      chatPanel.classList.remove("open");
    });

    sendChatBtn.addEventListener("click", handleSendChat);
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") handleSendChat();
    });
  }
});