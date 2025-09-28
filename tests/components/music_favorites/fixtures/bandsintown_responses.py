"""Test fixtures for Bandsintown LD+JSON responses.

Based on real LD+JSON data from https://www.bandsintown.com/a/6461184 (Vulvodynia)
Contains complete, realistic data for testing event extraction.
"""

# Real Vulvodynia events from Bandsintown LD+JSON
VULVODYNIA_EVENTS_LDJSON = [
    {
        "@context": "http://schema.org",
        "@type": "MusicEvent",
        "name": "Vulvodynia @ O2 Academy Islington",
        "startDate": "2025-11-25T18:00:00",
        "endDate": "2025-11-25",
        "url": "https://www.bandsintown.com/e/1036117971-vulvodynia-at-o2-academy-islington?came_from=209",
        "location": {
            "@type": "Place",
            "name": "O2 Academy Islington",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "United Kingdom",
                "addressRegion": "",
                "addressLocality": "London",
                "streetAddress": "N1 Centre 16 Parkfield St",
                "postalCode": "N1 0PS",
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": 51.5343501,
                "longitude": -0.1058837,
            },
        },
        "performer": {"@type": "PerformingGroup", "name": "Vulvodynia"},
        "description": "Vulvodynia",
        "image": "https://photos.bandsintown.com/thumb/11258982.jpeg",
        "eventAttendanceMode": "http://schema.org/OfflineEventAttendanceMode",
        "eventStatus": "http://schema.org/EventScheduled",
        "offers": {
            "@type": "Offer",
            "url": "https://www.bandsintown.com/e/1036117971-vulvodynia-at-o2-academy-islington?came_from=209",
            "availability": "https://schema.org/InStock",
            "validFrom": "2025-07-30T19:24:48Z",
        },
        "organizer": {
            "@type": "Organization",
            "name": "Vulvodynia",
            "url": "https://www.bandsintown.com/a/6461184-vulvodynia?came_from=209",
        },
    },
    {
        "@context": "http://schema.org",
        "@type": "MusicEvent",
        "name": "Vulvodynia @ Leeds University Stylus",
        "startDate": "2025-11-28T17:30:00",
        "endDate": "2025-11-28",
        "url": "https://www.bandsintown.com/e/1035095196-vulvodynia-at-leeds-university-stylus?came_from=209",
        "location": {
            "@type": "Place",
            "name": "Leeds University Stylus",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "United Kingdom",
                "addressRegion": "",
                "addressLocality": "Leeds",
                "streetAddress": "Leeds University Union,, Lifton Pl",
                "postalCode": "LS2 9JT",
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": 53.79648,
                "longitude": -1.54785,
            },
        },
        "performer": {"@type": "PerformingGroup", "name": "Vulvodynia"},
        "description": "Vulvodynia",
        "image": "https://photos.bandsintown.com/thumb/11258982.jpeg",
        "eventAttendanceMode": "http://schema.org/OfflineEventAttendanceMode",
        "eventStatus": "http://schema.org/EventScheduled",
        "offers": {
            "@type": "Offer",
            "url": "https://www.bandsintown.com/e/1035095196-vulvodynia-at-leeds-university-stylus?came_from=209",
            "availability": "https://schema.org/InStock",
            "validFrom": "2025-04-25T09:07:54Z",
        },
        "organizer": {
            "@type": "Organization",
            "name": "Vulvodynia",
            "url": "https://www.bandsintown.com/a/6461184-vulvodynia?came_from=209",
        },
    },
]

# Real Vulvodynia band info from Bandsintown LD+JSON
VULVODYNIA_BAND_LDJSON = {
    "@context": "http://schema.org",
    "@type": "MusicGroup",
    "name": "Vulvodynia",
    "location": {"@type": "Place", "name": "Johannesburg, South Africa"},
    "genre": "Slamming Deathcore",
    "sameAs": "https://www.shazam.com/artist/-/1032991537?utm_source=bandsintown",
    "employees": {
        "@type": "Person",
        "name": [
            "Lwandile Prusent",
            "Chris Van Der Walt",
            "Thomas Hughes",
            "Kris Xenopoulos",
            "Duncan Bentley",
            "Luke Haarhoff",
        ],
    },
    "description": "Looking in a medical textbook will tell you the following: Vulvodynia is a chronic, severe vaginal pain with no identifiable cause.",
    "interactionCount": "40207 Followers",
}

# Mixed LD+JSON data (both events and non-events)
MIXED_LDJSON_DATA = [
    VULVODYNIA_EVENTS_LDJSON[0],  # First event
    VULVODYNIA_BAND_LDJSON,  # Band info (not an event)
    VULVODYNIA_EVENTS_LDJSON[1],  # Second event
    {
        "@context": "http://schema.org",
        "@type": "Review",
        "reviewBody": "Great concert!",
        "reviewRating": {"@type": "Rating", "ratingValue": 5},
    },  # Review (not an event)
]
