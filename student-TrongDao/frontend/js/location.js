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

const recommendationSection = document.getElementById(
  "recommendation-section"
);

const savedPlacesSection = document.getElementById(
  "saved-places-section"
);


async function savedPlaceAuthHeaders(extraHeaders = {}) {
  if (window.jbSessionReady) {
    await window.jbSessionReady;
  }

  const token = localStorage.getItem("jb_token") || "";

  return {
    ...extraHeaders,
    "Authorization": `Bearer ${token}`
  };
}


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

  recommendationSection.hidden = false;
  showResultsMessage(
    recommendationResults,
    "Finding recommendations..."
  );

  scrollToSection(recommendationSection);

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
      responseData.recommendations
    );


  } catch (error) {
    formMessage.textContent = error.message;

    showResultsMessage(
      recommendationResults,
      "Recommendations could not be loaded."
    );
  }
});

function scrollToSection(section) {
  window.requestAnimationFrame(function () {
    section.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  });
}

function showResultsMessage(container, message) {
  const messageElement = document.createElement("p");
  messageElement.textContent = message;
  container.replaceChildren(messageElement);
}

function formatAiExplanation(explanation) {
  return explanation
    .replace(/\r\n/g, "\n")
    .replace(/#{1,6}\s*/g, "\n")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

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
    aiExplanation.textContent = formatAiExplanation(
      responseData.ai_explanation
    );
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

function displayRecommendations(recommendations) {
  recommendationResults.replaceChildren();

  if (recommendations.length === 0) {
    showResultsMessage(
      recommendationResults,
      "No attractions matched your preferences."
    );

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
  attractionId,
  saveButton
) {
  saveButton.disabled = true;
  saveButton.textContent = "Saving...";

  try {
    const headers = await savedPlaceAuthHeaders({
      "Content-Type": "application/json"
    });

    const response = await fetch(`${API_BASE_URL}/api/saved-places`, {
      method: "POST",
      headers,
      body: JSON.stringify({
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

  } catch (error) {
    saveButton.disabled = false;
    saveButton.textContent = "Save place";

    formMessage.textContent = error.message;
  }
}

loadSavedPlacesButton.addEventListener("click", function () {
  savedPlacesSection.hidden = false;
  scrollToSection(savedPlacesSection);
  loadSavedPlaces();
});


async function loadSavedPlaces() {
  showResultsMessage(
    savedPlacesResults,
    "Loading saved attractions..."
  );

  try {
    const headers = await savedPlaceAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/saved-places`,
      { headers }
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
    showResultsMessage(savedPlacesResults, error.message);
  }
}


function displaySavedPlaces(savedPlaces) {
  savedPlacesResults.replaceChildren();

  if (savedPlaces.length === 0) {
    showResultsMessage(
      savedPlacesResults,
      "No attractions have been saved yet."
    );

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
    const headers = await savedPlaceAuthHeaders({
      "Content-Type": "application/json"
    });

    const response = await fetch(
      `${API_BASE_URL}/api/saved-places/${savedPlace.saved_place_id}`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
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
    `Remove ${savedPlace.attraction_name} from saved attractions?`
  );

  if (!confirmed) {
    return;
  }

  deleteButton.disabled = true;
  deleteButton.textContent = "Removing...";
  statusMessage.textContent = "";

  try {
    const headers = await savedPlaceAuthHeaders();

    const response = await fetch(
      `${API_BASE_URL}/api/saved-places/${savedPlace.saved_place_id}`,
      {
        method: "DELETE",
        headers
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
      showResultsMessage(
        savedPlacesResults,
        "No attractions have been saved yet."
      );
    }

  } catch (error) {
    deleteButton.disabled = false;
    deleteButton.textContent = "Remove";
    statusMessage.textContent = error.message;
  }
}

const mcpForm = document.getElementById("mcp-form");
const mcpMode = document.getElementById("mcp-mode");
const mcpStatus = document.getElementById("mcp-status");
const mcpResult = document.getElementById("mcp-result");
const mcpSummary = document.getElementById("mcp-summary");
const mcpAttractions = document.getElementById(
  "mcp-attractions"
);

const ragForm = document.getElementById("rag-form");
const ragMode = document.getElementById("rag-mode");
const ragStatus = document.getElementById("rag-status");
const ragResult = document.getElementById("rag-result");
const ragAnswer = document.getElementById("rag-answer");
const ragConfidence = document.getElementById(
  "rag-confidence"
);
const ragCitations = document.getElementById(
  "rag-citations"
);


mcpForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  mcpResult.hidden = true;
  mcpAttractions.replaceChildren();

  if (!mcpMode.checked) {
    mcpStatus.textContent = "MCP Mode is disabled.";
    return;
  }

  const city = document.getElementById(
    "mcp-city"
  ).value.trim();

  const category = document.getElementById(
    "mcp-category"
  ).value;

  const argumentsData = {
    city
  };

  if (category) {
    argumentsData.category = category;
  }

  mcpStatus.textContent = "Running MCP tool...";

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/mcp/call`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-MCP-Mode": "on"
        },
        body: JSON.stringify({
          tool: "attractions_by_city",
          arguments: argumentsData
        })
      }
    );

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error ||
        "The MCP tool could not be executed."
      );
    }

    const toolResult = responseData.result || {};
    const structuredResult =
      toolResult.structuredContent;

    if (!structuredResult) {
      throw new Error(
        "The MCP server returned no structured result."
      );
    }

    displayMcpAttractions(structuredResult);

    mcpStatus.textContent =
      "MCP tool executed successfully.";

    mcpResult.hidden = false;

  } catch (error) {
    mcpStatus.textContent = error.message;
  }
});


function displayMcpAttractions(result) {
  const attractions = result.attractions || [];

  mcpSummary.textContent =
    `${result.count || attractions.length} attraction(s) ` +
    `returned for ${result.city}.`;

  mcpAttractions.replaceChildren();

  if (attractions.length === 0) {
    showResultsMessage(
      mcpAttractions,
      "No matching attractions were returned."
    );

    return;
  }

  for (const attraction of attractions) {
    const card = document.createElement("article");

    const heading = document.createElement("h4");
    heading.textContent = attraction.attraction_name;

    const category = document.createElement("p");
    category.textContent =
      `Category: ${attraction.category}`;

    const cost = document.createElement("p");
    cost.textContent =
      `Estimated cost: ${attraction.currency} ` +
      `$${attraction.estimated_cost}`;

    const accessibility = document.createElement("p");
    accessibility.textContent =
      `Accessibility: ` +
      `${attraction.accessibility_information}`;

    card.append(
      heading,
      category,
      cost,
      accessibility
    );

    mcpAttractions.appendChild(card);
  }
}


ragForm.addEventListener("submit", async function (event) {
  event.preventDefault();

  ragResult.hidden = true;
  ragCitations.replaceChildren();

  if (!ragMode.checked) {
    ragStatus.textContent = "RAG Mode is disabled.";
    return;
  }

  const query = document.getElementById(
    "rag-query"
  ).value.trim();

  ragStatus.textContent = "Retrieving grounded context...";

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/rag/answer`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-RAG-Mode": "on"
        },
        body: JSON.stringify({
          query,
          k: 5
        })
      }
    );

    const responseData = await response.json();

    if (!response.ok) {
      throw new Error(
        responseData.error ||
        "The RAG question could not be answered."
      );
    }

    displayRagResponse(responseData);

    if (responseData.status === "insufficient_context") {
      ragStatus.textContent =
        "RAG correctly returned insufficient context.";
    } else {
      ragStatus.textContent =
        "Grounded RAG response received.";
    }

    ragResult.hidden = false;

  } catch (error) {
    ragStatus.textContent = error.message;
  }
});


function displayRagResponse(responseData) {
  ragAnswer.textContent = responseData.answer;
  ragConfidence.textContent =
    responseData.confidence_category;

  ragCitations.replaceChildren();

  const citations = responseData.citations || [];

  if (citations.length === 0) {
    const item = document.createElement("li");
    item.textContent =
      "No source was cited because relevant context was unavailable.";

    ragCitations.appendChild(item);
    return;
  }

  for (const citation of citations) {
    const item = document.createElement("li");

    item.textContent =
      `${citation.source_id} — ` +
      `${citation.chunk_id} ` +
      `(${citation.authority_tier})`;

    ragCitations.appendChild(item);
  }
}
