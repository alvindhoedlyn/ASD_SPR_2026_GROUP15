const API_BASE_URL =
  `${window.location.protocol}//${window.location.hostname}:5104`;

const aiResponse = document.getElementById("ai-response");

const aiModels = document.getElementById("ai-models");

const aiExplanation = document.getElementById("ai-explanation");

const aiWarning = document.getElementById("ai-warning");

const aiDraft = document.getElementById("ai-draft");

const aiReview = document.getElementById("ai-review");

const loadSavedPlacesButton = document.getElementById(
  "load-saved-places"
);

const savedPlacesResults = document.getElementById(
  "saved-places-results"
);

const recommendationForm = document.getElementById(
  "recommendation-form"
);

const formMessage = document.getElementById("form-message");

const recommendationResults = document.getElementById(
  "recommendation-results"
);


recommendationForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  const selectedInterests = [];

  const interestCheckboxes = document.querySelectorAll(
    'input[name="interests"]:checked'
  );

  for (const checkbox of interestCheckboxes) {
    selectedInterests.push(checkbox.value);
  }

  if (selectedInterests.length === 0) {
    formMessage.textContent =
      "Please select at least one interest.";

    return;
  }

  const requestData = {
    journey_id: document.getElementById("journey-id").value,
    destination_city: document.getElementById(
      "destination-city"
    ).value,
    arrival_date: document.getElementById("arrival-date").value,
    departure_date: document.getElementById(
      "departure-date"
    ).value,
    interests: selectedInterests,
    weather_preferences: document.getElementById(
      "weather-preferences"
    ).value,
    crowd_tolerance: document.getElementById(
      "crowd-tolerance"
    ).value,
    budget_range: document.getElementById(
      "budget-range"
    ).value,
    accessibility_needs: document.getElementById(
      "accessibility-needs"
    ).value,
    ai_mode: document.getElementById("ai-mode").checked
  };

  formMessage.textContent = "Finding attractions...";

  recommendationResults.replaceChildren();

  aiResponse.hidden = true;
  aiModels.textContent = "";
  aiExplanation.textContent = "";
  aiWarning.textContent = "";
  aiDraft.textContent = "";
  aiReview.textContent = "";

  try {
    const response = await fetch(`${API_BASE_URL}/api/recommendations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(requestData)
    });

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error || "Could not create recommendations."
      );
    }

    formMessage.textContent =
      `${responseData.recommendation_count} attractions found.`;
      
    displayAiResponse(responseData);
    
    displayRecommendations(
      responseData.recommendations,
      requestData.journey_id
    );


  } catch (error) {
    formMessage.textContent = error.message;

    recommendationResults.textContent =
      "Recommendations could not be loaded.";
  }
});

function displayAiResponse(responseData) {
  if (responseData.mode !== "ai") {
    aiResponse.hidden = true;
    return;
  }

  aiResponse.hidden = false;

  aiModels.textContent =
    `Implementation agent: ${responseData.implementation_model} | ` +
    `Review agent: ${responseData.review_model}`;

  if (responseData.ai_explanation) {
    aiExplanation.textContent = responseData.ai_explanation;
  } else {
    aiExplanation.textContent =
      "No AI explanation was generated.";
  }

  const warnings = [];

  if (responseData.ai_error) {
    warnings.push(responseData.ai_error);
  }

  if (responseData.review_error) {
    warnings.push(responseData.review_error);
  }

  aiWarning.textContent = warnings.join(" ");

  aiDraft.textContent =
    responseData.ai_draft || "Qwen draft unavailable.";

  aiReview.textContent =
    responseData.ai_review || "Llama review unavailable.";
}

function displayRecommendations(recommendations, journeyId) {
  recommendationResults.replaceChildren();

  if (recommendations.length === 0) {
    recommendationResults.textContent =
      "No attractions matched your preferences.";

    return;
  }

  for (const place of recommendations) {
    const card = document.createElement("article");

    const heading = document.createElement("h3");
    heading.textContent = place.attraction_name;

    const location = document.createElement("p");
    location.textContent =
      `${place.city}, ${place.country}`;

    const category = document.createElement("p");
    category.textContent =
      `Category: ${place.category}`;

    const cost = document.createElement("p");
    cost.textContent =
      `Estimated cost: ${place.currency} $${place.estimated_cost}`;

    const duration = document.createElement("p");
    duration.textContent =
      `Expected duration: ${place.expected_duration_minutes} minutes`;

    const crowdLevel = document.createElement("p");
    crowdLevel.textContent =
      `Crowd level: ${place.crowd_level}`;

    const score = document.createElement("p");
    score.textContent =
      `Recommendation score: ${place.recommendation_score}`;

    const description = document.createElement("p");
    description.textContent = place.attraction_description;

    const reasonsHeading = document.createElement("h4");
    reasonsHeading.textContent = "Why it was recommended";

    const reasonsList = document.createElement("ul");

    for (const reason of place.recommendation_reasons) {
      const reasonItem = document.createElement("li");
      reasonItem.textContent = reason;
      reasonsList.appendChild(reasonItem);
    }

    const saveButton = document.createElement("button");
    saveButton.type = "button";
    saveButton.textContent = "Save place";

    saveButton.addEventListener("click", function () {
      saveAttraction(
        journeyId,
        place.attraction_id,
        saveButton
      );
    });

    card.append(
      heading,
      location,
      category,
      cost,
      duration,
      crowdLevel,
      score,
      description,
      reasonsHeading,
      reasonsList,
      saveButton
    );

    recommendationResults.appendChild(card);
  }
}


async function saveAttraction(
  journeyId,
  attractionId,
  saveButton
) {
  saveButton.disabled = true;
  saveButton.textContent = "Saving...";

  try {
    const response = await fetch(`${API_BASE_URL}/api/saved-places`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        journey_id: journeyId,
        attraction_id: attractionId,
        notes: ""
      })
    });

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error || "Could not save this place."
      );
    }

    saveButton.textContent = "Saved";

    await loadSavedPlaces(journeyId);

  } catch (error) {
    saveButton.disabled = false;
    saveButton.textContent = "Save place";

    formMessage.textContent = error.message;
  }
}

loadSavedPlacesButton.addEventListener("click", function () {
  const journeyId = document.getElementById(
    "journey-id"
  ).value.trim();

  if (!journeyId) {
    formMessage.textContent =
      "Enter a Journey ID before loading saved attractions.";

    return;
  }

  loadSavedPlaces(journeyId);
});


async function loadSavedPlaces(journeyId) {
  savedPlacesResults.textContent =
    "Loading saved attractions...";

  try {
    const response = await fetch(
        `${API_BASE_URL}/api/saved-places?journey_id=${
        encodeURIComponent(journeyId)
        }`
    );

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error ||
        "Could not load saved attractions."
      );
    }

    displaySavedPlaces(responseData);

  } catch (error) {
    savedPlacesResults.textContent = error.message;
  }
}


function displaySavedPlaces(savedPlaces) {
  savedPlacesResults.replaceChildren();

  if (savedPlaces.length === 0) {
    savedPlacesResults.textContent =
      "No attractions have been saved for this journey.";

    return;
  }

  for (const savedPlace of savedPlaces) {
    const card = document.createElement("article");

    const heading = document.createElement("h3");
    heading.textContent = savedPlace.attraction_name;

    const location = document.createElement("p");
    location.textContent =
      `${savedPlace.city}, ${savedPlace.country}`;

    const category = document.createElement("p");
    category.textContent =
      `Category: ${savedPlace.category}`;

    const cost = document.createElement("p");
    cost.textContent =
      `Estimated cost: ${savedPlace.currency} ` +
      `$${savedPlace.estimated_cost}`;

    const notesLabel = document.createElement("label");
    notesLabel.textContent = "Notes";

    const notesInput = document.createElement("input");
    notesInput.type = "text";
    notesInput.value = savedPlace.notes || "";
    notesInput.placeholder = "Add a note about this attraction";

    const updateButton = document.createElement("button");
    updateButton.type = "button";
    updateButton.textContent = "Update notes";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Remove";

    const statusMessage = document.createElement("p");
    statusMessage.setAttribute("role", "status");

    updateButton.addEventListener("click", function () {
      updateSavedPlace(
        savedPlace,
        notesInput.value,
        updateButton,
        statusMessage
      );
    });

    deleteButton.addEventListener("click", function () {
      deleteSavedPlace(
        savedPlace,
        card,
        deleteButton,
        statusMessage
      );
    });

    card.append(
      heading,
      location,
      category,
      cost,
      notesLabel,
      notesInput,
      updateButton,
      deleteButton,
      statusMessage
    );

    savedPlacesResults.appendChild(card);
  }
}


async function updateSavedPlace(
  savedPlace,
  newNotes,
  updateButton,
  statusMessage
) {
  updateButton.disabled = true;
  updateButton.textContent = "Updating...";
  statusMessage.textContent = "";

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/saved-places/${savedPlace.saved_place_id}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          journey_id: savedPlace.journey_id,
          attraction_id: savedPlace.attraction_id,
          notes: newNotes
        })
      }
    );

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error || "Could not update the notes."
      );
    }

    savedPlace.notes = newNotes;
    statusMessage.textContent = "Notes updated successfully.";

  } catch (error) {
    statusMessage.textContent = error.message;

  } finally {
    updateButton.disabled = false;
    updateButton.textContent = "Update notes";
  }
}


async function deleteSavedPlace(
  savedPlace,
  card,
  deleteButton,
  statusMessage
) {
  const confirmed = window.confirm(
    `Remove ${savedPlace.attraction_name} from this journey?`
  );

  if (!confirmed) {
    return;
  }

  deleteButton.disabled = true;
  deleteButton.textContent = "Removing...";
  statusMessage.textContent = "";

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/saved-places/${savedPlace.saved_place_id}`,
      {
        method: "DELETE"
      }
    );

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error ||
        "Could not remove the saved attraction."
      );
    }

    card.remove();

    if (savedPlacesResults.children.length === 0) {
      savedPlacesResults.textContent =
        "No attractions have been saved for this journey.";
    }

  } catch (error) {
    deleteButton.disabled = false;
    deleteButton.textContent = "Remove";
    statusMessage.textContent = error.message;
  }
}
