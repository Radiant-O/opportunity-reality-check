"""Small, deterministic gazetteer for mapping listing locations to countries and
checking whether a stated region includes a candidate's country.

Deliberately conservative: when we can't tell, we return ``None`` and the rules
engine reports the question as unknown rather than guessing.
"""

from __future__ import annotations

import re

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

COUNTRY_ALIASES: dict[str, str] = {
    "united states": "United States", "united states of america": "United States",
    "usa": "United States", "us": "United States", "u.s.": "United States",
    "u.s.a.": "United States", "america": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "u.k.": "United Kingdom",
    "great britain": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom",
    "uae": "United Arab Emirates", "united arab emirates": "United Arab Emirates",
    "south korea": "South Korea", "korea": "South Korea",
    "the netherlands": "Netherlands", "holland": "Netherlands",
    "czechia": "Czech Republic",
}

COUNTRIES = [
    "Nigeria", "United States", "India", "United Kingdom", "Canada", "Germany", "Brazil",
    "Kenya", "Ghana", "South Africa", "Egypt", "Pakistan", "Bangladesh", "Philippines",
    "Indonesia", "Mexico", "Argentina", "Colombia", "Chile", "Peru", "France", "Spain", "Italy",
    "Netherlands", "Belgium", "Poland", "Ukraine", "Turkey", "Israel", "United Arab Emirates",
    "Saudi Arabia", "Singapore", "Japan", "South Korea", "China", "Taiwan", "Hong Kong",
    "Australia", "New Zealand", "Ireland", "Portugal", "Sweden", "Norway", "Denmark", "Finland",
    "Switzerland", "Austria", "Czech Republic", "Romania", "Greece", "Hungary", "Vietnam",
    "Thailand", "Malaysia", "Morocco", "Ethiopia", "Rwanda", "Uganda", "Tanzania", "Estonia",
    "Lithuania", "Latvia", "Serbia", "Croatia", "Bulgaria", "Costa Rica", "Uruguay",
]
for _c in COUNTRIES:
    COUNTRY_ALIASES.setdefault(_c.lower(), _c)

CITY_COUNTRY: dict[str, str] = {
    "san francisco": "United States", "sf": "United States", "bay area": "United States",
    "new york": "United States", "nyc": "United States", "brooklyn": "United States",
    "los angeles": "United States", "seattle": "United States", "boston": "United States",
    "austin": "United States", "chicago": "United States", "miami": "United States",
    "palo alto": "United States", "menlo park": "United States", "mountain view": "United States",
    "san mateo": "United States", "san jose": "United States", "redwood city": "United States",
    "sunnyvale": "United States", "oakland": "United States", "berkeley": "United States",
    "denver": "United States", "atlanta": "United States", "washington, dc": "United States",
    "san diego": "United States", "dallas": "United States", "houston": "United States",
    "philadelphia": "United States", "pittsburgh": "United States", "salt lake city": "United States",
    "scotts valley": "United States", "santa monica": "United States", "el segundo": "United States",
    "london": "United Kingdom", "manchester": "United Kingdom", "cambridge, uk": "United Kingdom",
    "toronto": "Canada", "vancouver": "Canada", "montreal": "Canada", "waterloo": "Canada",
    "berlin": "Germany", "munich": "Germany", "paris": "France", "amsterdam": "Netherlands",
    "dublin": "Ireland", "lisbon": "Portugal", "madrid": "Spain", "barcelona": "Spain",
    "milan": "Italy", "rome": "Italy", "zurich": "Switzerland", "stockholm": "Sweden",
    "tel aviv": "Israel", "dubai": "United Arab Emirates", "bangalore": "India",
    "bengaluru": "India", "mumbai": "India", "delhi": "India", "hyderabad": "India",
    "lagos": "Nigeria", "abuja": "Nigeria", "nairobi": "Kenya", "accra": "Ghana",
    "cape town": "South Africa", "johannesburg": "South Africa", "cairo": "Egypt",
    "tokyo": "Japan", "seoul": "South Korea", "beijing": "China", "shanghai": "China",
    "shenzhen": "China", "sydney": "Australia", "melbourne": "Australia",
    "são paulo": "Brazil", "sao paulo": "Brazil", "mexico city": "Mexico",
    "buenos aires": "Argentina", "bogotá": "Colombia", "bogota": "Colombia",
    "warsaw": "Poland", "singapore": "Singapore", "hong kong": "Hong Kong",
    "taipei": "Taiwan", "bucharest": "Romania", "cluj": "Romania", "prague": "Czech Republic",
    "krakow": "Poland", "kraków": "Poland", "kyiv": "Ukraine", "istanbul": "Turkey",
    "copenhagen": "Denmark", "oslo": "Norway", "helsinki": "Finland", "vienna": "Austria",
    "brussels": "Belgium", "athens": "Greece", "budapest": "Hungary", "tallinn": "Estonia",
    "jakarta": "Indonesia", "manila": "Philippines", "bangkok": "Thailand", "kuala lumpur": "Malaysia",
    "ho chi minh city": "Vietnam", "hanoi": "Vietnam", "karachi": "Pakistan", "lahore": "Pakistan",
    "dhaka": "Bangladesh", "kigali": "Rwanda", "kampala": "Uganda", "addis ababa": "Ethiopia",
    "casablanca": "Morocco", "santiago": "Chile", "lima": "Peru", "medellín": "Colombia",
    "medellin": "Colombia", "montevideo": "Uruguay", "san josé": "Costa Rica", "riyadh": "Saudi Arabia",
    "abu dhabi": "United Arab Emirates", "auckland": "New Zealand", "osaka": "Japan",
}

# Regions -> member countries (only regions we can define unambiguously enough).
REGIONS: dict[str, set[str]] = {
    "European Union": {
        "Austria", "Belgium", "Bulgaria", "Croatia", "Czech Republic", "Denmark", "Estonia",
        "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia",
        "Lithuania", "Netherlands", "Poland", "Portugal", "Romania", "Spain", "Sweden",
    },
    "North America": {"United States", "Canada", "Mexico"},
    "Latin America": {
        "Mexico", "Brazil", "Argentina", "Colombia", "Chile", "Peru", "Costa Rica", "Uruguay",
    },
    "Africa": {
        "Nigeria", "Kenya", "Ghana", "South Africa", "Egypt", "Morocco", "Ethiopia", "Rwanda",
        "Uganda", "Tanzania",
    },
}
REGIONS["Europe"] = REGIONS["European Union"] | {
    "United Kingdom", "Switzerland", "Norway", "Ukraine", "Serbia",
}
REGIONS["EMEA"] = REGIONS["Europe"] | REGIONS["Africa"] | {
    "Israel", "Turkey", "United Arab Emirates", "Saudi Arabia", "Egypt",
}
REGIONS["Americas"] = REGIONS["North America"] | REGIONS["Latin America"]
REGIONS["APAC"] = {
    "India", "Singapore", "Japan", "South Korea", "China", "Taiwan", "Hong Kong", "Australia",
    "New Zealand", "Indonesia", "Philippines", "Vietnam", "Thailand", "Malaysia", "Pakistan",
    "Bangladesh",
}

REGION_ALIASES: dict[str, str] = {
    "eu": "European Union", "european union": "European Union", "europe": "Europe",
    "north america": "North America", "latam": "Latin America", "latin america": "Latin America",
    "south america": "Latin America", "emea": "EMEA", "americas": "Americas", "apac": "APAC",
    "asia pacific": "APAC", "asia-pacific": "APAC", "africa": "Africa",
}


def canonical_country(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower().rstrip(".")
    return COUNTRY_ALIASES.get(key) or COUNTRY_ALIASES.get(key + ".")


def canonical_region(name: str | None) -> str | None:
    """Return a canonical country or region name for free text, else None."""
    if not name:
        return None
    key = re.sub(r"\s+", " ", name.strip().lower()).strip(" .,;:()")
    key = re.sub(r"^the ", "", key)
    if key in REGION_ALIASES:
        return REGION_ALIASES[key]
    return canonical_country(key)


def infer_country(location: str | None) -> str | None:
    """Infer the country of a listing location like 'San Francisco, CA'.

    Returns None for remote/ambiguous/multi-country locations.
    """
    if not location:
        return None
    loc = location.strip()
    low = loc.lower()
    if low in {"remote", "anywhere", "worldwide", "global"}:
        return None

    found: set[str] = set()
    # Split on separators that commonly delimit multiple locations.
    for chunk in re.split(r"\s*(?:;|\||/| or | and |•)\s*", loc):
        c = _country_for_chunk(chunk)
        if c:
            found.add(c)
    if len(found) == 1:
        return found.pop()
    return None


def _country_for_chunk(chunk: str) -> str | None:
    chunk = chunk.strip()
    if not chunk:
        return None
    low = chunk.lower()
    parts = [p.strip() for p in chunk.split(",") if p.strip()]
    # Last comma part might be a country or US state.
    if len(parts) >= 2:
        last = parts[-1]
        c = canonical_country(last)
        if c:
            return c
        if last.upper() in US_STATES or last.title() in US_STATES.values():
            return "United States"
    c = canonical_country(low)
    if c:
        return c
    for city, country in CITY_COUNTRY.items():
        if re.search(rf"\b{re.escape(city)}\b", low):
            return country
    if low.title() in US_STATES.values():
        return "United States"
    return None


def region_includes(region: str, country: str) -> bool | None:
    """True/False when we can decide whether ``country`` is inside ``region``.

    ``region`` may be a country or a known region. Returns None when unknown.
    """
    r = canonical_region(region)
    c = canonical_country(country) or country.strip()
    if not r or not c:
        return None
    if r in REGIONS:
        return c in REGIONS[r]
    return r == c
