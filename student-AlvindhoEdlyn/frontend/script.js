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
    await fetchJourneys();
    await fetchTrips();
    setupEventListeners();
  }

  // -------------------------------------------------------------
  // Data Fetching Operations
  // -------------------------------------------------------------

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
          <p class="day-summary">${day.summary}</p>
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
          userId: 1
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
      activityGrid.innerHTML = `<p>${day.summary || "No activities specified."}</p>`;
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

    // Append user bubble
    appendChatBubble(question, "user");
    chatInput.value = "";

    // Build itinerary context from current trip
    let itineraryContext = "No active trip.";
    if (trips.length > 0 && trips[currentTripIndex]) {
      const trip = trips[currentTripIndex];
      itineraryContext = JSON.stringify(trip.days || []);
    }

    // Append typing placeholder
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

      if (!res.ok) throw new Error("AI Service error");

      const responseHtml = await res.text();
      typingBubble.innerHTML = responseHtml;
    } catch (err) {
      typingBubble.textContent = "Sorry, I had trouble processing that request.";
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
    regenerateTripBtn.addEventListener("click", () => {
      // Directs user back to new trip generation pre-filled
      showFrameState(generateFormState);
    });

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