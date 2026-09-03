// ===================== CONFIG =====================

const API_BASE = "http://localhost:5003";

function getUserId() {
    const username = localStorage.getItem("jb_username");
    if (!username) return 1;
    let hash = 0;
    for (let i = 0; i < username.length; i++) hash = (hash * 31 + username.charCodeAt(i)) % 100000;
    return hash || 1;
}
const USER_ID = getUserId();

let listings = [];
let priorities = { price: 50, location: 50, facility: 50, review: 50 };
let compareSelection = new Set();
let currentSort = "score";
let editingListingId = null;

// ===================== API HELPERS =====================

function apiUrl(path) {
    return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

async function apiGet(url) {
    const res = await fetch(apiUrl(url));
    if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
    return res.json();
}
async function apiSend(url, method, body) {
    const res = await fetch(apiUrl(url), {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`${method} ${url} failed: ${res.status}`);
    return res.json();
}

// ===================== LOAD DATA FROM BACKEND =====================

async function loadListings() {
    try {
        listings = await apiGet("/accommodations");
    } catch (e) {
        console.error("Failed to load accommodations:", e);
        listings = [];
    }
}

async function loadPriorities() {
    try {
        const p = await apiGet(`/priorities/${USER_ID}`);
        priorities = {
            price: p.price_weight,
            location: p.location_weight,
            facility: p.facility_weight,
            review: p.review_weight
        };
        ["price", "location", "facility", "review"].forEach(key => {
            document.getElementById(`w-${key}`).value = priorities[key];
            document.getElementById(`w-${key}-val`).textContent = `${priorities[key]}%`;
        });
    } catch (e) {
        console.error("Failed to load priorities:", e);
    }
}

// ===================== RECOMMENDATIONS (real API) =====================

async function fetchRecommendations() {
    try {
        const result = await apiSend("/recommendations", "POST", {
            user_id: USER_ID,
            city: selectedArea,
            desired_facilities: ["wifi", "pool", "breakfast"]
        });
        return result.recommendations || [];
    } catch (e) {
        console.error("Failed to fetch recommendations:", e);
        return [];
    }
}

async function renderResults() {
    document.getElementById("selected-area-label").textContent =
        selectedArea ? `Showing stays in ${selectedArea}` : "";

    const grid = document.getElementById("results-grid");
    let scored = await fetchRecommendations();

    if (currentSort === "price") scored.sort((a, b) => a.starting_price - b.starting_price);
    if (currentSort === "rating") scored.sort((a, b) => b.avg_rating - a.avg_rating);

    if (scored.length === 0) {
        grid.innerHTML = `<p class="panel-sub">No listings found for this area yet.</p>`;
        window._lastScored = [];
        return;
    }

    grid.innerHTML = scored.map(l => `
    <div class="stay-card" data-id="${l.accommodation_id}">
      <div class="stay-card-top">
        <h3>${l.name}</h3>
        <span class="stay-score">${Math.round(l.score * 100)}% match</span>
      </div>
      <p class="stay-city">${l.city_area}</p>
      <div class="stay-meta">
        <span>$${l.starting_price}/night</span>
        <span>★ ${l.avg_rating} (${l.review_count})</span>
      </div>
      <label class="compare-check" onclick="event.stopPropagation()">
        <input type="checkbox" class="compare-input" data-id="${l.accommodation_id}" ${compareSelection.has(l.accommodation_id) ? "checked" : ""}>
        Add to compare
      </label>
    </div>
  `).join("");

    grid.querySelectorAll(".stay-card").forEach(card => {
        card.addEventListener("click", () => openDetail(parseInt(card.dataset.id)));
    });
    grid.querySelectorAll(".compare-input").forEach(input => {
        input.addEventListener("change", (e) => {
            const id = parseInt(e.target.dataset.id);
            if (e.target.checked) compareSelection.add(id); else compareSelection.delete(id);
            updateCompareButton();
        });
    });

    window._lastScored = scored;
}

function updateCompareButton() {
    const btn = document.getElementById("compare-btn");
    btn.textContent = `Compare selected (${compareSelection.size})`;
    btn.disabled = compareSelection.size < 2;
}

// ===================== PRIORITY SLIDERS =====================

["price", "location", "facility", "review"].forEach(key => {
    const slider = document.getElementById(`w-${key}`);
    const label = document.getElementById(`w-${key}-val`);
    slider.addEventListener("input", () => {
        priorities[key] = parseInt(slider.value);
        label.textContent = `${slider.value}%`;
    });
    slider.addEventListener("change", renderResults);
});

document.getElementById("save-priorities").addEventListener("click", async () => {
    try {
        await apiSend(`/priorities/${USER_ID}`, "PUT", {
            price_weight: priorities.price,
            location_weight: priorities.location,
            facility_weight: priorities.facility,
            review_weight: priorities.review
        });
        alert("Priorities saved.");
        renderResults();
    } catch (e) {
        alert("Failed to save priorities. Check the backend is running.");
    }
});

document.getElementById("sort-select").addEventListener("change", (e) => {
    currentSort = e.target.value;
    renderResults();
});

// ===================== DETAIL VIEW =====================

async function openDetail(id) {
    const [listing, rooms] = await Promise.all([
        apiGet(`/accommodations/${id}`),
        apiGet(`/accommodations/${id}/rooms`)
    ]);

    const scoredMatch = (window._lastScored || []).find(l => l.accommodation_id === id);

    const content = document.getElementById("detail-content");
    content.innerHTML = `
    <h2>${listing.name}</h2>
    <p class="detail-city">${listing.city_area}</p>
    <p>${listing.description || ""}</p>
    <div class="detail-section">
      <h4>Facilities</h4>
      <div class="stay-facilities">${listing.facilities.map(f => `<span class="chip">${f}</span>`).join("")}</div>
    </div>
    <div class="detail-section">
      <h4>Rooms</h4>
      ${rooms.map(r => `<div class="room-row"><span>${r.room_name}</span><span>$${r.price_per_night}/night</span></div>`).join("")}
    </div>
    <div class="detail-section">
      <h4>Reviews</h4>
      <p>★ ${listing.avg_rating} average from ${listing.review_count} reviews</p>
    </div>
    ${scoredMatch ? `
      <div class="detail-section">
        <button class="btn-secondary" id="explain-btn">Overview</button>
        <div id="explain-box"></div>
      </div>
    ` : ""}
  `;
    document.getElementById("detail-modal").hidden = false;

    if (scoredMatch) {
        document.getElementById("explain-btn").addEventListener("click", async () => {
            const box = document.getElementById("explain-box");
            box.innerHTML = `<div class="explain-box">Thinking...</div>`;
            try {
                const result = await apiSend("/recommendations/explain", "POST", {
                    name: listing.name,
                    city_area: listing.city_area,
                    starting_price: scoredMatch.starting_price,
                    avg_rating: listing.avg_rating,
                    review_count: listing.review_count,
                    facilities: listing.facilities,
                    score: scoredMatch.score,
                    breakdown: scoredMatch.breakdown
                });
                box.innerHTML = `<div class="explain-box">${result.explanation || result.error}</div>`;
            } catch (e) {
                box.innerHTML = `<div class="explain-box">Failed to reach the AI agent.</div>`;
            }
        });
    }
}
document.getElementById("detail-close").addEventListener("click", () => {
    document.getElementById("detail-modal").hidden = true;
});

// ===================== COMPARATOR =====================

document.getElementById("compare-close").addEventListener("click", () => {
    document.getElementById("compare-modal").hidden = true;
});

// ===================== TABS =====================

document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        if (btn.dataset.tab === "manage" && !requireAdmin()) return;

        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
        if (btn.dataset.tab === "manage") renderManageTable();
    });
});

// ===================== MANAGE LISTINGS (real CRUD) =====================

async function renderManageTable() {
    await loadListings();
    const tbody = document.getElementById("manage-tbody");
    tbody.innerHTML = listings.map(l => `
    <tr data-id="${l.accommodation_id}">
      <td>${l.name}</td>
      <td>${l.city_area}</td>
      <td>★ ${l.avg_rating}</td>
      <td>${l.accommodation_id}</td>
      <td class="row-actions">
        <button class="edit-btn" data-id="${l.accommodation_id}">Edit</button>
        <button class="delete-btn" data-id="${l.accommodation_id}">Delete</button>
      </td>
    </tr>
  `).join("");

    tbody.querySelectorAll(".edit-btn").forEach(btn => {
        btn.addEventListener("click", () => openListingForm(parseInt(btn.dataset.id)));
    });
    tbody.querySelectorAll(".delete-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            if (!confirm("Delete this listing?")) return;
            await apiSend(`/accommodations/${btn.dataset.id}`, "DELETE", {});
            renderManageTable();
            renderResults();
        });
    });
}

document.getElementById("add-listing-btn").addEventListener("click", () => openListingForm(null));

async function openListingForm(id) {
    editingListingId = id;
    const form = document.getElementById("listing-form");
    const title = document.getElementById("listing-form-title");
    const roomsSection = document.getElementById("rooms-section");

    if (id) {
        const l = await apiGet(`/accommodations/${id}`);
        title.textContent = "Edit listing";
        document.getElementById("f-id").value = l.accommodation_id;
        document.getElementById("f-name").value = l.name;
        document.getElementById("f-city").value = l.city_area;
        document.getElementById("f-desc").value = l.description || "";
        document.getElementById("f-facilities").value = l.facilities.join(", ");
        document.getElementById("f-price").value = 0;
        document.getElementById("f-rating").value = l.avg_rating;

        await renderRoomsSection(id);
    } else {
        title.textContent = "Add listing";
        form.reset();
        document.getElementById("f-id").value = "";
        roomsSection.hidden = true;   // no rooms until the listing is created and saved
    }
    document.getElementById("listing-form-modal").hidden = false;
}

document.getElementById("listing-form-close").addEventListener("click", () => {
    document.getElementById("listing-form-modal").hidden = true;
});

document.getElementById("listing-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const facilities = document.getElementById("f-facilities").value.split(",").map(f => f.trim()).filter(Boolean);
    const data = {
        name: document.getElementById("f-name").value,
        city_area: document.getElementById("f-city").value,
        description: document.getElementById("f-desc").value,
        facilities,
        avg_rating: parseFloat(document.getElementById("f-rating").value) || 0,
        review_count: 0,
        images: []
    };

    const id = document.getElementById("f-id").value;
    const price = parseFloat(document.getElementById("f-price").value) || 0;

    try {
        if (id) {
            await apiSend(`/accommodations/${id}`, "PUT", data);
        } else {
            const created = await apiSend("/accommodations", "POST", data);
            if (price > 0) {
                await apiSend(`/accommodations/${created.accommodation_id}/rooms`, "POST", {
                    room_name: "Standard room",
                    price_per_night: price,
                    available_rooms: 1,
                    capacity: 2
                });
            }
        }
        document.getElementById("listing-form-modal").hidden = true;
        renderManageTable();
        renderResults();
    } catch (err) {
        alert("Failed to save listing. Check the backend is running.");
    }
});

document.getElementById("compare-btn").addEventListener("click", async () => {
    const selected = (window._lastScored || []).filter(l => compareSelection.has(l.accommodation_id));
    const wrap = document.getElementById("compare-table-wrap");

    // Fetch rooms for each selected listing
    wrap.innerHTML = `<p class="panel-sub">Loading room details…</p>`;
    document.getElementById("compare-modal").hidden = false;

    const roomsByListing = await Promise.all(
        selected.map(l => apiGet(`/accommodations/${l.accommodation_id}/rooms`).catch(() => []))
    );

    wrap.innerHTML = `
    <table class="compare-table">
      <thead><tr><th>Listing</th>${selected.map(l => `<th>${l.name}</th>`).join("")}</tr></thead>
      <tbody>
        <tr><td>City / area</td>${selected.map(l => `<td>${l.city_area}</td>`).join("")}</tr>
        <tr><td>Starting price/night</td>${selected.map(l => `<td>$${l.starting_price}</td>`).join("")}</tr>
        <tr><td>Rating</td>${selected.map(l => `<td>★ ${l.avg_rating} (${l.review_count} reviews)</td>`).join("")}</tr>
        <tr><td>Facilities</td>${selected.map(l => `<td>${(l.facilities || []).join(", ") || "—"}</td>`).join("")}</tr>
        <tr>
          <td>Rooms</td>
          ${roomsByListing.map(rooms => `
            <td>
              ${rooms.length
            ? `<ul class="compare-room-list">${rooms.map(r =>
                `<li>${r.room_name} — $${r.price_per_night}/night (sleeps ${r.capacity}, ${r.available_rooms} available)</li>`
            ).join("")}</ul>`
            : "No rooms listed"}
            </td>
          `).join("")}
        </tr>
        <tr><td><strong>Overall match</strong></td>${selected.map(l => `<td><strong>${Math.round(l.score * 100)}%</strong></td>`).join("")}</tr>
      </tbody>
    </table>
    <div id="compare-explain" class="explain-box loading">Thinking...</div>
  `;

    try {
        const result = await apiSend("/recommendations/explain-compare", "POST", {
            items: selected.map(l => ({
                name: l.name,
                breakdown: l.breakdown,
                starting_price: l.starting_price,
                city_area: l.city_area,
                avg_rating: l.avg_rating,
                review_count: l.review_count,
                facilities: l.facilities,
                score: l.score
            }))
        });
        const box = document.getElementById("compare-explain");
        box.classList.remove("loading");
        box.textContent = result.explanation || result.error;
    } catch (e) {
        const box = document.getElementById("compare-explain");
        box.classList.remove("loading");
        box.textContent = "Failed to reach the AI agent. Check that Ollama is running.";
    }
});

let selectedArea = null;

async function loadAreas() {
    try {
        return await apiGet("/areas");
    } catch (e) {
        console.error("Failed to load areas:", e);
        return [];
    }
}

async function showAreaSelect() {
    return new Promise(async (resolve) => {
        const container = document.getElementById("area-options");
        container.innerHTML = `<p class="panel-sub">Loading areas…</p>`;
        document.getElementById("area-select-modal").hidden = false;

        const areas = await loadAreas();

        if (areas.length === 0) {
            container.innerHTML = `<p class="panel-sub">Couldn't load areas. Check the backend is running.</p>`;
            return;
        }

        container.innerHTML = areas.map((a, i) =>
            `<button class="area-option-btn" data-area="${a}">${i + 1}. ${a}</button>`
        ).join("");

        container.querySelectorAll(".area-option-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                selectedArea = btn.dataset.area;
                document.getElementById("area-select-modal").hidden = true;
                resolve();
            });
        });
    });
}

document.getElementById("change-area-btn").addEventListener("click", async () => {
    await showAreaSelect();
    renderResults();
});

async function renderRoomsSection(accommodationId) {
    const section = document.getElementById("rooms-section");
    section.hidden = false;

    const rooms = await apiGet(`/accommodations/${accommodationId}/rooms`);
    const list = document.getElementById("rooms-list");

    list.innerHTML = rooms.map(r => `
    <div class="room-item" data-room-id="${r.room_id}">
      <div class="room-item-row1">
        <input class="room-item-name" type="text" value="${r.room_name || ""}" data-field="room_name" placeholder="Room name">
      </div>
      <div class="room-item-row2">
        <div>
          <label>Price/night</label>
          <input type="number" value="${r.price_per_night}" min="0" data-field="price_per_night">
        </div>
        <div>
          <label>Capacity</label>
          <input type="number" value="${r.capacity}" min="1" data-field="capacity">
        </div>
        <div>
          <label>Available</label>
          <input type="number" value="${r.available_rooms}" min="0" data-field="available_rooms">
        </div>
        <div class="room-item-actions">
          <button class="save-room-btn">Save</button>
          <button class="delete-room-btn">Delete</button>
        </div>
      </div>
    </div>
  `).join("") || `<p class="panel-sub">No rooms yet — add one below.</p>`;

    list.querySelectorAll(".room-item").forEach(item => {
        const roomId = item.dataset.roomId;

        item.querySelector(".save-room-btn").addEventListener("click", async () => {
            const data = {
                room_name: item.querySelector('[data-field="room_name"]').value,
                price_per_night: parseFloat(item.querySelector('[data-field="price_per_night"]').value) || 0,
                capacity: parseInt(item.querySelector('[data-field="capacity"]').value) || 1,
                available_rooms: parseInt(item.querySelector('[data-field="available_rooms"]').value) || 0,
            };
            try {
                await apiSend(`/rooms/${roomId}`, "PUT", data);
                renderResults();
            } catch (e) {
                alert("Failed to save room.");
            }
        });

        item.querySelector(".delete-room-btn").addEventListener("click", async () => {
            if (!confirm("Delete this room?")) return;
            try {
                await apiSend(`/rooms/${roomId}`, "DELETE", {});
                renderRoomsSection(accommodationId);
                renderResults();
            } catch (e) {
                alert("Failed to delete room.");
            }
        });
    });
}
document.getElementById("add-room-btn").addEventListener("click", async () => {
    const accommodationId = document.getElementById("f-id").value;
    if (!accommodationId) return;

    const name = document.getElementById("new-room-name").value.trim();
    const price = parseFloat(document.getElementById("new-room-price").value) || 0;
    const capacity = parseInt(document.getElementById("new-room-capacity").value) || 2;
    const available = parseInt(document.getElementById("new-room-available").value) || 1;

    if (!name || price <= 0) {
        alert("Enter a room name and a price greater than 0.");
        return;
    }

    try {
        await apiSend(`/accommodations/${accommodationId}/rooms`, "POST", {
            room_name: name,
            price_per_night: price,
            capacity,
            available_rooms: available
        });
        document.getElementById("new-room-name").value = "";
        document.getElementById("new-room-price").value = "";
        document.getElementById("new-room-capacity").value = 2;
        document.getElementById("new-room-available").value = 1;
        renderRoomsSection(accommodationId);
        renderResults();
    } catch (e) {
        alert("Failed to add room.");
    }
});

// ===================== INIT =====================

(async function init() {
    await window.jbSessionReady;

    if (!isAdmin()) {
        const manageBtn = document.getElementById("manage-tab-btn");
        if (manageBtn) manageBtn.hidden = true;
    }

    await showAreaSelect();     // sets selectedArea
    await loadListings();
    await loadPriorities();
    await renderResults();      // fetches /recommendations filtered by selectedArea
})();