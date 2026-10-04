"""
Corpus loader for the Itinerary Planner feature.

Builds one RAG chunk per activity. Every location has 2 outdoor and 2 indoor
activities so the planner can pick by weather. Registered in rag_pipeline.py's
build_corpus() exactly like corpus_accommodation.py.

The activity data below is a curated draft. Before relying on it, check each
entry against a reference source (e.g. Wikivoyage or the official park/venue
site) and update source_id in load_itinerary_chunks() to point at that source.
Entries for very remote places (Kata Tjuta, Kings Canyon, Coral Bay, Turquoise
Bay, Cape Tribulation) have limited indoor options and deserve extra checking.

Chunk text is deliberately short and labelled, because the downstream model
(qwen2.5:0.5b) copes much better with compact, structured context.
"""

from __future__ import annotations

import re

# ===================== WEATHER VOCABULARY =====================
# Must match the weather labels your backend produces (WEATHER_POOL).

OUTDOOR_WEATHER = ["Sunny", "Clear", "Partly Cloudy", "Breezy", "Overcast"]
INDOOR_WEATHER = ["Light Rain", "Thunderstorms", "Tropical Downpour", "Windy", "Foggy", "Overcast"]

# "any" means: do not filter, return both indoor and outdoor activities.
_WEATHER_TO_SETTING = {
    "sunny": "outdoor",
    "clear": "outdoor",
    "partly cloudy": "outdoor",
    "breezy": "outdoor",
    "overcast": "any",
    "light rain": "indoor",
    "thunderstorms": "indoor",
    "windy": "indoor",
    "foggy": "indoor",
    "tropical downpour": "indoor",
}


def setting_for_weather(weather: str | None) -> str:
    """Map a weather label to 'outdoor', 'indoor' or 'any' (unknown -> 'any')."""
    return _WEATHER_TO_SETTING.get((weather or "").strip().lower(), "any")


# ===================== ACTIVITY DATA =====================
# Each activity: (name, category, duration, description)

ITINERARY_DATA = {
    # ---------- Journey 1: Sydney Weekend ----------
    "Bondi Beach": {
        "journey_id": 1, "region": "Sydney", "state": "NSW",
        "outdoor": [
            ("Swim or surf lesson at Bondi Beach", "beach", "2-3 hours",
             "Swim between the flags or book a surf lesson on Sydney's most famous beach."),
            ("Bondi to Coogee coastal walk", "walking", "2-3 hours",
             "Clifftop path past ocean pools, bays and sandstone headlands."),
        ],
        "indoor": [
            ("Brunch at a Campbell Parade cafe", "food", "1-2 hours",
             "Beachside cafes along Campbell Parade serving brunch and coffee."),
            ("Bondi Pavilion gallery and theatre", "culture", "1 hour",
             "Beachfront heritage building with a gallery, theatre and community spaces."),
        ],
    },
    "Opera House": {
        "journey_id": 1, "region": "Sydney", "state": "NSW",
        "outdoor": [
            ("Opera House forecourt and Bennelong Point walk", "sightseeing", "1 hour",
             "Harbourside walk with classic views of the sails and the Harbour Bridge."),
            ("Royal Botanic Garden to Mrs Macquarie's Chair", "walking", "1-2 hours",
             "Harbour-edge garden path ending at a famous Opera House viewpoint."),
        ],
        "indoor": [
            ("Sydney Opera House guided tour", "culture", "1 hour",
             "Behind-the-scenes tour of the theatres and the building's history."),
            ("Attend a performance at the Opera House", "culture", "2-3 hours",
             "See an opera, concert or theatre show in one of the venues."),
        ],
    },
    "Blue Mountains": {
        "journey_id": 1, "region": "Sydney", "state": "NSW",
        "outdoor": [
            ("Three Sisters at Echo Point lookout", "scenic", "1 hour",
             "Iconic rock formation with views over the Jamison Valley from Katoomba."),
            ("Grand Canyon Track walk near Blackheath", "hiking", "3-4 hours",
             "Rainforest and cliff-edge walk through a sandstone gorge."),
        ],
        "indoor": [
            ("Blue Mountains Cultural Centre", "culture", "1-2 hours",
             "Katoomba art gallery with local history and World Heritage exhibitions."),
            ("Cafes and shops on Leura Mall", "shopping", "1-2 hours",
             "Village strip of cafes, boutiques and bookshops in Leura."),
        ],
    },
    "Harbour Bridge": {
        "journey_id": 1, "region": "Sydney", "state": "NSW",
        "outdoor": [
            ("BridgeClimb over the Harbour Bridge", "adventure", "3-4 hours",
             "Guided climb to the summit arch with wide harbour views."),
            ("Walk across the Harbour Bridge", "sightseeing", "45 minutes",
             "Free pedestrian walkway between Milsons Point and The Rocks."),
        ],
        "indoor": [
            ("Pylon Lookout exhibition and viewing deck", "sightseeing", "1 hour",
             "History exhibits inside the pylon plus a viewing deck at the top."),
            ("Museum of Contemporary Art Australia", "museum", "1-2 hours",
             "Contemporary art museum at Circular Quay, close to the bridge."),
        ],
    },

    # ---------- Journey 2: Melbourne Foodie Trip ----------
    "Queen Victoria Market": {
        "journey_id": 2, "region": "Melbourne", "state": "VIC",
        "outdoor": [
            ("Open-air stalls at Queen Victoria Market", "shopping", "1-2 hours",
             "Covered open-air sheds selling produce, clothing and souvenirs."),
            ("Hosier Lane street art walk", "walking", "1 hour",
             "Laneway walk through Melbourne's best-known street art."),
        ],
        "indoor": [
            ("Deli Hall tasting at Queen Victoria Market", "food", "1 hour",
             "Cheese, cured meats and pastries in the market's covered Deli Hall."),
            ("State Library Victoria domed reading room", "culture", "1 hour",
             "Historic domed reading room and free exhibitions in the CBD."),
        ],
    },
    "St Kilda": {
        "journey_id": 2, "region": "Melbourne", "state": "VIC",
        "outdoor": [
            ("St Kilda Pier and penguin watching", "wildlife", "1-2 hours",
             "Walk the pier and breakwater, with little penguins at dusk."),
            ("Luna Park rides", "entertainment", "2-3 hours",
             "Historic beachside amusement park with a classic scenic railway."),
        ],
        "indoor": [
            ("Acland Street cake shops", "food", "1 hour",
             "Famous strip of European-style cake shops and cafes."),
            ("Jewish Museum of Australia", "museum", "1-2 hours",
             "Museum of Jewish history and culture on Alma Road."),
        ],
    },
    "Yarra Valley": {
        "journey_id": 2, "region": "Melbourne", "state": "VIC",
        "outdoor": [
            ("Hot air balloon flight over the Yarra Valley", "adventure", "3 hours",
             "Sunrise balloon flight over vineyards, weather permitting."),
            ("Healesville Sanctuary wildlife walk", "wildlife", "3-4 hours",
             "Meet kangaroos, koalas and platypus in bushland enclosures."),
        ],
        "indoor": [
            ("Cellar door wine tasting in the Yarra Valley", "food", "1-2 hours",
             "Taste cool-climate pinot noir and chardonnay at a cellar door."),
            ("Yarra Valley Chocolaterie and Ice Creamery", "food", "1 hour",
             "Chocolate tasting and ice cream at a Yarra Glen chocolaterie."),
        ],
    },

    # ---------- Journey 3: Tropical North Queensland ----------
    "Great Barrier Reef": {
        "journey_id": 3, "region": "Tropical North Queensland", "state": "QLD",
        "outdoor": [
            ("Snorkel or dive the Great Barrier Reef", "water", "full day",
             "Reef boat trip from Cairns or Port Douglas with snorkelling and diving."),
            ("Glass-bottom boat or semi-submersible reef tour", "water", "1-2 hours",
             "See coral and fish without getting wet."),
        ],
        "indoor": [
            ("Cairns Aquarium", "wildlife", "2 hours",
             "Aquarium showcasing Great Barrier Reef and rainforest ecosystems."),
            ("Reef Teach marine talk in Cairns", "education", "2 hours",
             "Evening talk by marine biologists on reef ecology and conservation."),
        ],
    },
    "Daintree Rainforest": {
        "journey_id": 3, "region": "Tropical North Queensland", "state": "QLD",
        "outdoor": [
            ("Daintree River wildlife cruise", "wildlife", "1-2 hours",
             "Spot saltwater crocodiles, birds and tree snakes from a river boat."),
            ("Mossman Gorge rainforest walk", "hiking", "1-2 hours",
             "Rainforest tracks and swimming spots at Mossman Gorge."),
        ],
        "indoor": [
            ("Daintree Discovery Centre", "education", "1-2 hours",
             "Rainforest interpretive centre with a canopy tower and aerial walkway."),
            ("Mossman Gorge Centre", "culture", "1 hour",
             "Indigenous art shop, cafe and cultural displays at the gorge entrance."),
        ],
    },
    "Cape Tribulation": {
        "journey_id": 3, "region": "Tropical North Queensland", "state": "QLD",
        "outdoor": [
            ("Jindalba Boardwalk rainforest walk", "walking", "30 minutes",
             "Short boardwalk loop through lowland rainforest."),
            ("Cape Tribulation Beach walk", "beach", "1 hour",
             "Rainforest meets reef; stay out of the water due to crocodiles and stingers."),
        ],
        "indoor": [
            ("Cape Tribulation Exotic Fruit Farm tasting", "food", "1-2 hours",
             "Taste rare tropical fruits and ice creams on a farm visit."),
            ("Cafe lunch in Cape Tribulation", "food", "1 hour",
             "Rainforest-setting cafes and restaurants near the beach."),
        ],
    },
    "Kuranda": {
        "journey_id": 3, "region": "Tropical North Queensland", "state": "QLD",
        "outdoor": [
            ("Skyrail Rainforest Cableway", "scenic", "1.5 hours one way",
             "Gondola ride above the rainforest canopy to Kuranda village."),
            ("Barron Falls lookout", "scenic", "1 hour",
             "Lookout over Barron Gorge, at its best after the wet season."),
        ],
        "indoor": [
            ("Australian Butterfly Sanctuary", "wildlife", "1 hour",
             "Walk through a large enclosed aviary of free-flying butterflies."),
            ("Kuranda Koala Gardens", "wildlife", "1 hour",
             "Meet koalas, wombats and wallabies in a small wildlife park."),
        ],
    },

    # ---------- Journey 4: Red Centre Adventure ----------
    "Uluru": {
        "journey_id": 4, "region": "Red Centre", "state": "NT",
        "outdoor": [
            ("Uluru base walk", "hiking", "3-4 hours",
             "10.6 km loop around the rock passing waterholes and rock art."),
            ("Sunrise viewing at Talinguru Nyakunytjaku", "scenic", "2 hours",
             "Dune viewing area for sunrise over Uluru and Kata Tjuta."),
        ],
        "indoor": [
            ("Uluru-Kata Tjuta Cultural Centre", "culture", "1-2 hours",
             "Anangu art, stories and exhibitions near the park entrance."),
            ("Dot painting workshop", "culture", "2 hours",
             "Learn Anangu dot painting with local artists at the Cultural Centre."),
        ],
    },
    "Kata Tjuta": {
        "journey_id": 4, "region": "Red Centre", "state": "NT",
        "outdoor": [
            ("Valley of the Winds walk", "hiking", "3-4 hours",
             "7.4 km loop between the domes; may close in extreme heat."),
            ("Walpa Gorge walk", "hiking", "1 hour",
             "Easy 2.6 km return walk between two large domes."),
        ],
        "indoor": [
            ("Cultural Centre exhibits on Anangu stories", "culture", "1-2 hours",
             "Learn the Tjukurpa stories linked to Uluru and Kata Tjuta."),
            ("Maruku Arts gallery at the Cultural Centre", "shopping", "1 hour",
             "Anangu-owned arts gallery selling artworks and crafts."),
        ],
    },
    "Kings Canyon": {
        "journey_id": 4, "region": "Red Centre", "state": "NT",
        "outdoor": [
            ("Kings Canyon Rim Walk", "hiking", "3-4 hours",
             "6 km rim loop with canyon views; start early, closed on very hot days."),
            ("Kings Creek Walk", "hiking", "1 hour",
             "Easy 2.6 km return walk along the canyon floor."),
        ],
        "indoor": [
            ("Dinner at Kings Canyon Resort", "food", "1-2 hours",
             "Outback dining at the resort near the canyon."),
            ("Kings Canyon Resort bar and lounge", "relaxation", "1-2 hours",
             "Sit back and unwind out of the heat."),
        ],
    },
    "Alice Springs": {
        "journey_id": 4, "region": "Red Centre", "state": "NT",
        "outdoor": [
            ("Alice Springs Desert Park", "wildlife", "3-4 hours",
             "Desert wildlife, nocturnal house and bird shows on the edge of town."),
            ("Simpsons Gap walk", "hiking", "1-2 hours",
             "Rock waterhole and rock wallabies in the West MacDonnell Ranges."),
        ],
        "indoor": [
            ("Araluen Cultural Precinct", "culture", "1-2 hours",
             "Galleries and museums of Central Australian art and history."),
            ("Royal Flying Doctor Service Tourist Facility", "museum", "1 hour",
             "Museum and tour about outback medical care."),
        ],
    },

    # ---------- Journey 5: Tasmanian Wilderness ----------
    "Cradle Mountain": {
        "journey_id": 5, "region": "Tasmania", "state": "TAS",
        "outdoor": [
            ("Dove Lake circuit", "hiking", "2 hours",
             "6 km lakeside loop with views of Cradle Mountain."),
            ("Marion's Lookout", "hiking", "3-4 hours",
             "Steep climb to views over Dove Lake and the mountain."),
        ],
        "indoor": [
            ("Cradle Mountain Visitor Centre", "education", "1 hour",
             "Park information, exhibits and maps at the Cradle Valley entrance."),
            ("Lodge dining in Cradle Valley", "food", "1-2 hours",
             "Warm meal by the fire at a lodge restaurant in the valley."),
        ],
    },
    "Freycinet National Park": {
        "journey_id": 5, "region": "Tasmania", "state": "TAS",
        "outdoor": [
            ("Wineglass Bay Lookout walk", "hiking", "1-2 hours",
             "Uphill walk to a classic view over the curved bay."),
            ("Cape Tourville lighthouse walk", "scenic", "30 minutes",
             "Short boardwalk to coastal cliff views."),
        ],
        "indoor": [
            ("Freycinet Marine Farm oyster tasting", "food", "1 hour",
             "Fresh oysters and seafood at Coles Bay."),
            ("Freycinet Visitor Centre", "education", "30 minutes",
             "Park information and displays at the entrance."),
        ],
    },
    "Mona Museum": {
        "journey_id": 5, "region": "Tasmania", "state": "TAS",
        "outdoor": [
            ("Ferry ride from Hobart to Mona", "scenic", "30 minutes",
             "Fast boat up the Derwent River to the museum's jetty."),
            ("Mona grounds and vineyard walk", "walking", "1 hour",
             "Lawns, sculptures and vines around the museum."),
        ],
        "indoor": [
            ("Mona art collection", "museum", "2-3 hours",
             "Large underground collection of ancient and contemporary art."),
            ("Wine and food at Mona", "food", "1-2 hours",
             "Tasmanian wines and food at the on-site winery and bars."),
        ],
    },
    "Port Arthur": {
        "journey_id": 5, "region": "Tasmania", "state": "TAS",
        "outdoor": [
            ("Port Arthur Historic Site grounds walk", "history", "2-3 hours",
             "Explore convict-era ruins and gardens on the peninsula."),
            ("Port Arthur harbour cruise", "scenic", "25 minutes",
             "Short cruise around the bay past the Isle of the Dead."),
        ],
        "indoor": [
            ("Port Arthur Asylum museum", "museum", "1 hour",
             "Exhibits on convict life in the former asylum building."),
            ("Port Arthur Visitor Centre exhibition and cafe", "education", "1 hour",
             "Interpretive displays and a cafe at the site entrance."),
        ],
    },

    # ---------- Journey 6: Perth & Rottnest Island ----------
    "Kings Park": {
        "journey_id": 6, "region": "Perth", "state": "WA",
        "outdoor": [
            ("Lotterywest Federation Walkway", "scenic", "1 hour",
             "Glass-and-steel walkway through the treetops with river views."),
            ("Western Australian Botanic Garden walk", "walking", "1-2 hours",
             "Native plants and spring wildflowers overlooking the city."),
        ],
        "indoor": [
            ("Aspects of Kings Park gallery", "shopping", "1 hour",
             "Gallery and shop selling Western Australian art and crafts."),
            ("Restaurant or cafe with city views", "food", "1-2 hours",
             "Dine with views over the Swan River and the city skyline."),
        ],
    },
    "Cottesloe Beach": {
        "journey_id": 6, "region": "Perth", "state": "WA",
        "outdoor": [
            ("Swim and snorkel at Cottesloe Beach", "beach", "2-3 hours",
             "White-sand beach with a rocky reef nearby."),
            ("Sunset on the Cottesloe foreshore", "scenic", "1 hour",
             "Watch the sun set over the Indian Ocean from the grass or sand."),
        ],
        "indoor": [
            ("Indiana Tea House", "food", "1-2 hours",
             "Beachfront cafe and restaurant in a heritage-style building."),
            ("Drinks at Cottesloe Beach Hotel", "food", "1-2 hours",
             "Ocean-view pub known for sunset drinks."),
        ],
    },
    "Rottnest Island": {
        "journey_id": 6, "region": "Perth", "state": "WA",
        "outdoor": [
            ("Cycle around Rottnest Island", "cycling", "3-5 hours",
             "Car-free island loop past beaches, salt lakes and lighthouses."),
            ("Snorkel at Little Salmon Bay", "water", "1-2 hours",
             "Sheltered bay with fish and a marked snorkel trail."),
        ],
        "indoor": [
            ("Rottnest Island Museum (Wadjemup)", "museum", "1 hour",
             "Island history from Aboriginal heritage to the wartime period."),
            ("Meal at the Hotel Rottnest", "food", "1-2 hours",
             "Island pub and restaurant near Thomson Bay."),
        ],
    },
    "Fremantle Markets": {
        "journey_id": 6, "region": "Perth", "state": "WA",
        "outdoor": [
            ("Fishing Boat Harbour and Bathers Beach stroll", "walking", "1-2 hours",
             "Harbourside walk with seafood eateries and a small beach."),
            ("Fremantle Round House walk", "history", "1 hour",
             "Visit Western Australia's oldest surviving public building and its harbour views."),
        ],
        "indoor": [
            ("Fremantle Markets browse", "shopping", "1-2 hours",
             "Historic covered market with food, crafts and souvenirs, typically open Friday to Sunday."),
            ("Western Australian Maritime Museum", "museum", "1-2 hours",
             "Shipwreck and seafaring exhibitions on Victoria Quay."),
        ],
    },

    # ---------- Journey 7: Barossa Wine & Culture ----------
    "Tanunda": {
        "journey_id": 7, "region": "Barossa Valley", "state": "SA",
        "outdoor": [
            ("Cycle the Barossa Trail", "cycling", "2-3 hours",
             "Flat sealed trail linking towns and vineyards."),
            ("Whispering Wall at Barossa Reservoir", "sightseeing", "1 hour",
             "Dam wall where whispers carry across the curve."),
        ],
        "indoor": [
            ("Barossa Regional Gallery", "culture", "1 hour",
             "Local and touring art exhibitions in Tanunda."),
            ("German-style bakeries on Murray Street", "food", "1 hour",
             "Baked goods and cafes on Tanunda's historic main street."),
        ],
    },
    "Barossa Valley Vineyards": {
        "journey_id": 7, "region": "Barossa Valley", "state": "SA",
        "outdoor": [
            ("Vineyard walk and picnic", "walking", "2 hours",
             "Walk between the vines and picnic at a winery estate."),
            ("E-bike vineyard tour", "cycling", "3 hours",
             "Guided electric bike ride between cellar doors and vineyards."),
        ],
        "indoor": [
            ("Shiraz cellar door tasting", "food", "1-2 hours",
             "Taste the Barossa's signature bold Shiraz."),
            ("Long lunch at a winery restaurant", "food", "2-3 hours",
             "Regional produce paired with local wines."),
        ],
    },
    "Adelaide Central Market": {
        "journey_id": 7, "region": "Adelaide", "state": "SA",
        "outdoor": [
            ("Adelaide Botanic Garden walk", "walking", "1-2 hours",
             "Free garden on North Terrace with a large glasshouse."),
            ("River Torrens Riverbank walk", "walking", "1 hour",
             "Riverside path past Adelaide Oval and city parks."),
        ],
        "indoor": [
            ("Adelaide Central Market food tasting", "food", "1-2 hours",
             "Covered market with produce, cheese, coffee and street food."),
            ("Art Gallery of South Australia", "museum", "1-2 hours",
             "Large state collection of Australian and international art."),
        ],
    },
    "Hahndorf": {
        "journey_id": 7, "region": "Adelaide Hills", "state": "SA",
        "outdoor": [
            ("Hahndorf Main Street heritage stroll", "walking", "1-2 hours",
             "German-settler village with historic buildings and boutiques."),
            ("Beerenberg Farm strawberry picking", "food", "1-2 hours",
             "Pick-your-own strawberries in season, roughly November to April."),
        ],
        "indoor": [
            ("Hahndorf Academy", "culture", "1 hour",
             "Art gallery and museum in a historic building."),
            ("German Cake Shop", "food", "30 minutes",
             "Traditional German cakes and coffee on the main street."),
        ],
    },

    # ---------- Journey 8: Great Ocean Road ----------
    "Twelve Apostles": {
        "journey_id": 8, "region": "Great Ocean Road", "state": "VIC",
        "outdoor": [
            ("Twelve Apostles viewing platforms", "scenic", "1 hour",
             "Boardwalk lookouts over the limestone sea stacks."),
            ("Gibson Steps to the beach", "scenic", "1 hour",
             "Steep steps down to the sand beneath towering cliffs."),
        ],
        "indoor": [
            ("Twelve Apostles Visitor Centre", "education", "30 minutes",
             "Displays and a cafe at the main lookout precinct."),
            ("Port Campbell cafes and fish and chips", "food", "1 hour",
             "Seaside town nearby with cafes and fresh seafood."),
        ],
    },
    "Lorne": {
        "journey_id": 8, "region": "Great Ocean Road", "state": "VIC",
        "outdoor": [
            ("Erskine Falls walk", "hiking", "1 hour",
             "Waterfall viewing platform in the Otway rainforest."),
            ("Teddy's Lookout", "scenic", "30 minutes",
             "Lookout over the Erskine River valley and the coast."),
        ],
        "indoor": [
            ("Qdos Arts gallery and cafe", "culture", "1-2 hours",
             "Gallery, sculpture garden and cafe in the bush near Lorne."),
            ("Cafes on Mountjoy Parade", "food", "1 hour",
             "Seaside cafes and bakeries along Lorne's main street."),
        ],
    },
    "Bells Beach": {
        "journey_id": 8, "region": "Great Ocean Road", "state": "VIC",
        "outdoor": [
            ("Bells Beach surf lookout", "scenic", "1 hour",
             "Watch surfers from the cliff platform at this famous break."),
            ("Surf lesson at Torquay", "water", "2 hours",
             "Beginner-friendly surf lessons at nearby Torquay."),
        ],
        "indoor": [
            ("Australian National Surfing Museum", "museum", "1 hour",
             "Surfing history and classic boards at Surf City Plaza, Torquay."),
            ("Surf outlet shopping at Surf City Plaza", "shopping", "1-2 hours",
             "Surf brand outlet stores in Torquay."),
        ],
    },
    "Loch Ard Gorge": {
        "journey_id": 8, "region": "Great Ocean Road", "state": "VIC",
        "outdoor": [
            ("Loch Ard Gorge beach and lookouts", "scenic", "1 hour",
             "Sheltered beach and cliff paths tied to a famous shipwreck story."),
            ("Tom and Eva Lookout", "scenic", "30 minutes",
             "Short walk to viewpoints over the gorge and coast."),
        ],
        "indoor": [
            ("Flagstaff Hill Maritime Museum", "museum", "2-3 hours",
             "Warrnambool museum village holding relics from the Loch Ard shipwreck."),
            ("Timboon Railway Shed Distillery", "food", "1 hour",
             "Whisky and produce tasting in a converted railway shed."),
        ],
    },

    # ---------- Journey 9: Darwin & Top End ----------
    "Kakadu National Park": {
        "journey_id": 9, "region": "Top End", "state": "NT",
        "outdoor": [
            ("Yellow Water Billabong cruise", "wildlife", "2 hours",
             "Boat cruise for crocodiles and birdlife at sunrise or sunset."),
            ("Ubirr rock art and lookout walk", "culture", "2 hours",
             "Aboriginal rock art galleries and sunset views over the floodplain."),
        ],
        "indoor": [
            ("Warradjan Aboriginal Cultural Centre", "culture", "1-2 hours",
             "Exhibitions on local Aboriginal culture near Cooinda."),
            ("Bowali Visitor Centre", "education", "1 hour",
             "Park information, films and displays near Jabiru."),
        ],
    },
    "Litchfield National Park": {
        "journey_id": 9, "region": "Top End", "state": "NT",
        "outdoor": [
            ("Wangi Falls swim", "water", "1-2 hours",
             "Plunge pool below twin waterfalls; check that swimming is open."),
            ("Buley Rockhole", "water", "1-2 hours",
             "Cascading rock pools for a natural spa-style swim."),
        ],
        "indoor": [
            ("Territory Wildlife Park aquarium", "wildlife", "1 hour",
             "Walk-through aquarium with barramundi and other Top End fish, on the road from Darwin."),
            ("Territory Wildlife Park nocturnal house", "wildlife", "1 hour",
             "Indoor house for night-active Top End animals."),
        ],
    },
    "Mindil Beach": {
        "journey_id": 9, "region": "Darwin", "state": "NT",
        "outdoor": [
            ("Mindil Beach Sunset Market", "food", "2-3 hours",
             "Dry-season evening food and craft stalls by the beach, roughly April to October."),
            ("Sunset at Mindil Beach", "scenic", "1 hour",
             "Watch a Top End sunset over the Beagle Gulf."),
        ],
        "indoor": [
            ("Museum and Art Gallery of the Northern Territory", "museum", "2 hours",
             "Aboriginal art, natural history and a Cyclone Tracy exhibit."),
            ("Crocosaurus Cove", "wildlife", "1-2 hours",
             "Crocodile and reptile attraction in Darwin's city centre."),
        ],
    },
    "Katherine Gorge": {
        "journey_id": 9, "region": "Top End", "state": "NT",
        "outdoor": [
            ("Nitmiluk Gorge cruise", "scenic", "2-4 hours",
             "Boat cruise through the sandstone gorges."),
            ("Baruwei Lookout walk", "hiking", "2 hours",
             "Short hike to a lookout over the gorge."),
        ],
        "indoor": [
            ("Nitmiluk Visitor Centre", "education", "1 hour",
             "Park information and displays on Jawoyn culture."),
            ("Katherine Museum", "museum", "1 hour",
             "Local history museum in Katherine town."),
        ],
    },

    # ---------- Journey 10: Ningaloo Reef Explorer ----------
    "Exmouth": {
        "journey_id": 10, "region": "Ningaloo Coast", "state": "WA",
        "outdoor": [
            ("Swim with whale sharks", "wildlife", "full day",
             "Seasonal Ningaloo tours, roughly March to August."),
            ("Vlamingh Head Lighthouse sunset", "scenic", "1 hour",
             "Lookout over the Indian Ocean and Ningaloo Reef."),
        ],
        "indoor": [
            ("Ningaloo Centre", "education", "1-2 hours",
             "Exhibitions and aquarium about Ningaloo Reef and marine life."),
            ("Seafood lunch in Exmouth", "food", "1 hour",
             "Local seafood cafes and restaurants in town."),
        ],
    },
    "Coral Bay": {
        "journey_id": 10, "region": "Ningaloo Coast", "state": "WA",
        "outdoor": [
            ("Snorkel the Coral Bay house reef", "water", "2 hours",
             "Snorkel straight off the beach at Bill's Bay."),
            ("Manta ray swim tour", "wildlife", "half day",
             "Boat tour to swim with manta rays."),
        ],
        "indoor": [
            ("Coral Bay village cafes and pubs", "food", "1 hour",
             "Casual meals in the compact Coral Bay village."),
            ("Coral Bay tour offices and shops", "shopping", "30 minutes",
             "Plan reef and manta ray tours and pick up snorkel gear."),
        ],
    },
    "Cape Range National Park": {
        "journey_id": 10, "region": "Ningaloo Coast", "state": "WA",
        "outdoor": [
            ("Yardie Creek gorge walk and boat tour", "scenic", "2 hours",
             "Sandstone gorge with rock wallabies and a boat cruise."),
            ("Mandu Mandu Gorge walk", "hiking", "2 hours",
             "3 km loop through a dry gorge above the coast."),
        ],
        "indoor": [
            ("Milyering Discovery Centre", "education", "1 hour",
             "Visitor centre inside the park with exhibits on Ningaloo and Cape Range."),
            ("Ningaloo Centre in Exmouth", "education", "1-2 hours",
             "Exhibitions and aquarium at the Exmouth centre."),
        ],
    },
    "Turquoise Bay": {
        "journey_id": 10, "region": "Ningaloo Coast", "state": "WA",
        "outdoor": [
            ("The Drift snorkel", "water", "1-2 hours",
             "Float along a current over coral; for confident swimmers."),
            ("Turquoise Bay beach day", "beach", "2-3 hours",
             "White sand and clear water for swimming and relaxing."),
        ],
        "indoor": [
            ("Milyering Discovery Centre", "education", "1 hour",
             "Visitor centre inside the park with exhibits on Ningaloo and Cape Range."),
            ("Ningaloo Centre in Exmouth", "education", "1-2 hours",
             "Exhibitions and aquarium at the Exmouth centre."),
        ],
    },
}

KNOWN_LOCATIONS = list(ITINERARY_DATA)
_LOCATION_LOOKUP = {name.lower(): name for name in ITINERARY_DATA}


def canonical_location(name: str | None) -> str | None:
    """Return the exact location key for a (case-insensitive) name, or None."""
    return _LOCATION_LOOKUP.get((name or "").strip().lower())


# ===================== QUERY UNDERSTANDING =====================
# Turns a free-text question ("what can I do at Bondi when it's raining?")
# into structured filters (place + indoor/outdoor). Deterministic: no LLM and
# no extra dependencies, so it is fast and gives the same answer every time.

# Generic trailing words dropped to build short aliases ("Kakadu National Park" -> "kakadu").
_ALIAS_SUFFIXES = ("national park", "museum", "markets", "market", "rainforest", "gorge", "beach", "island", "mountain")
# Common alternative names people type.
_EXTRA_ALIASES = {
    "ayers rock": "Uluru",
    "olgas": "Kata Tjuta",
    "harbor bridge": "Harbour Bridge",
    "12 apostles": "Twelve Apostles",
    "barrier reef": "Great Barrier Reef",
    "wineglass bay": "Freycinet National Park",
    "mossman gorge": "Daintree Rainforest",
}

_INDOOR_WORDS = {"indoor", "indoors", "inside", "covered"}
_OUTDOOR_WORDS = {"outdoor", "outdoors", "outside"}
SETTING_WORDS = _INDOOR_WORDS | _OUTDOOR_WORDS  # these DO appear in chunk text ("Setting: indoor")
# Weather words that are not exact WEATHER_POOL labels but imply a setting.
_WET_OR_POOR_VIEW_WORDS = {
    "rain", "rains", "rainy", "raining", "drizzle", "shower", "showers", "storm", "storms", "stormy",
    "thunder", "lightning", "downpour", "monsoon", "wind", "windy", "gusty", "fog", "foggy", "mist", "misty",
}
_FINE_WEATHER_WORDS = {"sunny", "sunshine", "sun", "breezy", "breeze"}


# Conversational filler that carries no search signal for itinerary questions.
# Ignored when ranking so words like "near" or "things" (or the "s" left over from
# "it's") can't create false matches against chunk text, and so they don't count
# against query_coverage. Weather words are included too: they are applied as an
# indoor/outdoor filter instead of being matched against text. Used ONLY by
# itinerary search, so accommodation retrieval is unaffected.
QUERY_FILLER = {
    "i", "me", "my", "we", "us", "our", "you", "your", "it", "its", "s", "t", "ll", "m", "re", "ve", "d",
    "do", "does", "did", "can", "could", "should", "would", "will", "want", "need", "like", "love", "get", "go",
    "going", "see", "visit", "try", "find", "show", "tell", "give", "recommend", "suggest",
    "thing", "things", "something", "anything", "stuff", "idea", "ideas", "option", "options",
    "activity", "activities", "place", "places", "spot", "spots",
    "good", "best", "great", "nice", "fun", "cool", "popular", "top",
    "any", "some", "there", "here", "about", "when", "who", "how", "where", "why", "was", "be", "been",
    "near", "nearby", "around", "close", "day", "days", "today", "tomorrow", "trip", "please", "just",
    "really", "very", "also", "so", "not", "no", "but", "as", "by", "up", "than", "then", "too",
    "if", "this", "that", "these", "those", "have", "has", "had", "am", "were", "may", "might", "must",
    "while", "during", "after", "before", "over", "into", "out", "off", "all", "each", "every", "more",
    "most", "much", "many", "other", "only", "ok", "okay", "plan", "planning", "look", "looking", "help",
} | _WET_OR_POOR_VIEW_WORDS | _FINE_WEATHER_WORDS


def _norm(text: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _build_location_phrases() -> dict[str, str]:
    phrases: dict[str, str] = {}
    for name in ITINERARY_DATA:
        phrases[_norm(name)] = name
    for name in ITINERARY_DATA:
        full = _norm(name)
        for suffix in _ALIAS_SUFFIXES:
            if full.endswith(" " + suffix):
                short = full[: -len(suffix)].strip()
                if short and short not in phrases:
                    phrases[short] = name
    phrases.update({k: v for k, v in _EXTRA_ALIASES.items() if v in ITINERARY_DATA})
    return phrases


_LOCATION_PHRASES = _build_location_phrases()
_REGION_PHRASES = {_norm(info["region"]): info["region"] for info in ITINERARY_DATA.values()}


def _extract(phrases: dict[str, str], text: str) -> tuple[list[str], str, list[str]]:
    """
    Find whole-word phrases (longest first) and remove them so shorter ones can't
    re-match inside. Returns (canonical names found, remaining text, phrases consumed).
    """
    found: list[str] = []
    used: list[str] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        needle = f" {phrase} "
        if needle in text:
            if phrases[phrase] not in found:
                found.append(phrases[phrase])
            used.append(phrase)
            text = text.replace(needle, " ")
    return found, text, used


def _single(values: set[str]) -> str | None:
    return next(iter(values)) if len(values) == 1 else None


def parse_itinerary_query(query: str) -> dict:
    """
    Returns {"locations": [...], "regions": [...], "setting": "indoor"|"outdoor"|None,
    "place_words": [...]}  (place_words = the words of the place phrases that were matched).

    - locations: known location names found in the question (full names or aliases).
    - regions: only looked for when no location was found (e.g. "things to do in Sydney").
    - setting: an explicit "indoor"/"outdoor" wins; otherwise inferred from weather
      words ("raining" -> indoor, "sunny" -> outdoor). Overcast, mixed or conflicting
      signals give None, which means "show both".
    """
    text = " " + _norm(query) + " "
    locations, text, used = _extract(_LOCATION_PHRASES, text)
    regions: list[str] = []
    if not locations:
        regions, text, used = _extract(_REGION_PHRASES, text)
    place_words = sorted({word for phrase in used for word in phrase.split()})

    tokens = set(text.split())
    explicit: set[str] = set()
    if tokens & _INDOOR_WORDS:
        explicit.add("indoor")
    if tokens & _OUTDOOR_WORDS:
        explicit.add("outdoor")

    weather: set[str] = set()
    for label, setting in _WEATHER_TO_SETTING.items():  # exact labels such as "light rain"
        if f" {label} " in text:
            weather.add(setting)
    if tokens & _WET_OR_POOR_VIEW_WORDS:
        weather.add("indoor")
    if tokens & _FINE_WEATHER_WORDS:
        weather.add("outdoor")
    weather.discard("any")

    setting = _single(explicit) if explicit else _single(weather)
    return {"locations": locations, "regions": regions, "setting": setting, "place_words": place_words}


# ===================== RESULT GRADING (for top-5 / precision@5) =====================

def grade_result(meta: dict, matched_terms, content_terms: set[str], parsed: dict):
    """
    Grades one itinerary chunk against what the question asked for.

    A chunk is RELEVANT when it matches ALL of:
      - place:   the named location (or named region)
      - setting: the indoor/outdoor setting implied by the question's weather words
      - content: at least one of the question's remaining content words (only if it has any)

    Returns None if the chunk should be left out entirely; otherwise
    (penalty, place_level, mismatch) where lower penalty = closer match and
    `mismatch` lists what differs (empty list = relevant).

    When a place is named, mismatches are soft: they only push a chunk lower, which
    is how a top-5 list can be filled with the next-best options (same region, then
    same state, or the other setting). With no place named, setting and content
    mismatches are hard exclusions, so unrelated chunks are never used as filler.
    """
    setting = parsed.get("setting")
    setting_ok = setting is None or meta.get("setting") == setting
    content_ok = (not content_terms) or bool(set(matched_terms) & content_terms)

    if parsed["locations"]:
        regions = {ITINERARY_DATA[name]["region"] for name in parsed["locations"]}
        states = {ITINERARY_DATA[name]["state"] for name in parsed["locations"]}
        if meta.get("location") in parsed["locations"]:
            place_level = 0
        elif meta.get("region") in regions:
            place_level = 1
        elif meta.get("state") in states:
            place_level = 2
        else:
            return None
    elif parsed["regions"]:
        states = {info["state"] for info in ITINERARY_DATA.values() if info["region"] in parsed["regions"]}
        if meta.get("region") in parsed["regions"]:
            place_level = 0
        elif meta.get("state") in states:
            place_level = 2
        else:
            return None
    else:
        if not (setting_ok and content_ok):
            return None
        place_level = 0

    mismatch = []
    if place_level:
        mismatch.append("place")
    if not setting_ok:
        mismatch.append("setting")
    if not content_ok:
        mismatch.append("content")
    penalty = place_level + 2 * (not setting_ok) + 2 * (not content_ok)
    return penalty, place_level, mismatch


# ===================== CHUNK LOADER =====================

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_itinerary_chunks() -> list[dict]:
    """One chunk per activity, in the same shape as the accommodation chunks."""
    chunks: list[dict] = []
    for location, info in ITINERARY_DATA.items():
        for setting in ("outdoor", "indoor"):
            weather = ", ".join(OUTDOOR_WEATHER if setting == "outdoor" else INDOOR_WEATHER)
            for n, (name, category, duration, description) in enumerate(info[setting], start=1):
                text = (
                    f"Activity: {name}. "
                    f"Location: {location}, {info['region']}, {info['state']}. "
                    f"Setting: {setting}. Category: {category}. "
                    f"Best weather: {weather}. Duration: {duration}. "
                    f"Description: {description}"
                )
                chunks.append({
                    "chunk_id": f"itinerary_{_slug(location)}_{setting}_{n}",
                    "source_id": f"itinerary-curated:{_slug(location)}",
                    "authority_tier": "tier_2",
                    "text": text,
                    "metadata": {
                        "source_type": "itinerary",
                        "location": location,
                        "region": info["region"],
                        "state": info["state"],
                        "journey_id": info["journey_id"],
                        "setting": setting,
                        "category": category,
                        "activity": name,
                    },
                })
    return chunks