"""Reading a location string, which is harder than it looks and matters more.

The location field is the most reliable statement of where a job may be done,
and the first two versions of this filter both failed on it the same way: they
matched only *bare* names, so anything compound fell through to a default of
"region" and reached the dashboard.

    "Cardiff, London or Remote (UK)"     -> called region. It is UK-only.
    "USA, Canada, Argentina, Mexico, Peru" -> called region, because Argentina
                                            and Peru were missing from the
                                            country list, so an `all()` test
                                            failed open.

Both are the same mistake: **an unrecognised token made the check pass.** So
this module fails closed. A location it cannot parse is reported as unknown
and the caller falls back to reading prose, rather than being handed a
confident wrong answer.

The country lists are not exhaustive and never will be. What matters is that
the *unknown* case is handled explicitly instead of by accident.
"""

from __future__ import annotations

import re

GLOBAL = "global"
REGION = "region"
COUNTRY = "country"
UNKNOWN = "unknown"

# Cities mapped to their country, so "Cardiff, London" resolves to one place
# rather than to two unrecognised tokens.
CITY_COUNTRY = {
    "london": "uk", "cardiff": "uk", "manchester": "uk", "edinburgh": "uk",
    "bristol": "uk", "cambridge": "uk", "oxford": "uk", "leeds": "uk",
    "berlin": "germany", "munich": "germany", "münchen": "germany",
    "hamburg": "germany", "cologne": "germany", "köln": "germany",
    "frankfurt": "germany", "stuttgart": "germany", "düsseldorf": "germany",
    "paris": "france", "lyon": "france", "toulouse": "france",
    "madrid": "spain", "barcelona": "spain", "valencia": "spain",
    "lisbon": "portugal", "lisboa": "portugal", "porto": "portugal",
    "amsterdam": "netherlands", "rotterdam": "netherlands", "utrecht": "netherlands",
    "brussels": "belgium", "antwerp": "belgium",
    "dublin": "ireland", "cork": "ireland",
    "stockholm": "sweden", "gothenburg": "sweden",
    "copenhagen": "denmark", "oslo": "norway", "helsinki": "finland",
    "warsaw": "poland", "krakow": "poland", "kraków": "poland", "wroclaw": "poland",
    "prague": "czechia", "brno": "czechia",
    "vienna": "austria", "zurich": "switzerland", "zürich": "switzerland",
    "geneva": "switzerland", "basel": "switzerland",
    "milan": "italy", "rome": "italy", "turin": "italy",
    "bucharest": "romania", "cluj": "romania", "sofia": "bulgaria",
    "budapest": "hungary", "athens": "greece", "tallinn": "estonia",
    "vilnius": "lithuania", "riga": "latvia",
    "new york": "usa", "san francisco": "usa", "seattle": "usa", "austin": "usa",
    "boston": "usa", "chicago": "usa", "los angeles": "usa", "denver": "usa",
    # The Bay Area and the other US hubs postings name without a state or country. Without
    # them 35 US roles ("San Jose", "New York City", "US-CA-Menlo Park") sat in the target
    # lens as "country not stated".
    "new york city": "usa", "nyc": "usa", "brooklyn": "usa", "san jose": "usa",
    "sunnyvale": "usa", "san mateo": "usa", "palo alto": "usa", "menlo park": "usa",
    "redwood city": "usa", "mountain view": "usa", "cupertino": "usa", "santa clara": "usa",
    "oakland": "usa", "berkeley": "usa", "bay area": "usa", "san francisco bay": "usa",
    "sf": "usa", "bellevue": "usa", "redmond": "usa", "washington dc": "usa",
    "atlanta": "usa", "miami": "usa", "san diego": "usa", "pittsburgh": "usa",
    "philadelphia": "usa", "houston": "usa", "dallas": "usa", "salt lake city": "usa",
    "boulder": "usa", "raleigh": "usa",
    "toronto": "canada", "vancouver": "canada", "montreal": "canada", "ottawa": "canada",
    "waterloo": "canada", "calgary": "canada", "edmonton": "canada",
    "tel aviv": "israel", "bangalore": "india", "bengaluru": "india",
    "mumbai": "india", "delhi": "india", "hyderabad": "india", "pune": "india",
    "singapore": "singapore", "sydney": "australia", "melbourne": "australia",
    "tokyo": "japan", "são paulo": "brazil", "sao paulo": "brazil",
    # Gulf
    "dubai": "uae", "abu dhabi": "uae", "sharjah": "uae", "masdar city": "uae",
    "riyadh": "saudi arabia", "jeddah": "saudi arabia", "dammam": "saudi arabia",
    "neom": "saudi arabia", "khobar": "saudi arabia", "dhahran": "saudi arabia",
    "doha": "qatar", "kuwait city": "kuwait", "manama": "bahrain",
    "muscat": "oman",
    # Pakistan
    "lahore": "pakistan", "karachi": "pakistan", "islamabad": "pakistan",
    "rawalpindi": "pakistan", "faisalabad": "pakistan", "peshawar": "pakistan",
    "multan": "pakistan", "quetta": "pakistan", "sialkot": "pakistan",
    "gujranwala": "pakistan",
    # East and Southeast Asia
    "beijing": "china", "shanghai": "china", "shenzhen": "china", "hangzhou": "china",
    "guangzhou": "china", "chengdu": "china", "nanjing": "china", "wuhan": "china",
    "suzhou": "china", "xian": "china", "tianjin": "china",
    "hong kong": "hong kong", "kowloon": "hong kong", "taipei": "taiwan",
    "hsinchu": "taiwan", "seoul": "south korea", "pangyo": "south korea",
    "busan": "south korea", "osaka": "japan", "kyoto": "japan", "fukuoka": "japan",
    "yokohama": "japan", "kuala lumpur": "malaysia", "petaling jaya": "malaysia",
    "penang": "malaysia", "cyberjaya": "malaysia", "johor bahru": "malaysia",
    "jakarta": "indonesia", "bandung": "indonesia", "surabaya": "indonesia",
    "bangkok": "thailand", "chiang mai": "thailand", "ho chi minh city": "vietnam",
    "ho chi minh": "vietnam", "hcmc": "vietnam", "hanoi": "vietnam", "da nang": "vietnam",
    "manila": "philippines", "makati": "philippines", "taguig": "philippines",
    "cebu": "philippines", "dhaka": "bangladesh", "chennai": "india", "kolkata": "india",
    "gurgaon": "india", "gurugram": "india", "noida": "india", "ahmedabad": "india",
    # more of Europe
    "eindhoven": "netherlands", "the hague": "netherlands", "delft": "netherlands",
    "ghent": "belgium", "leuven": "belgium", "aarhus": "denmark", "malmo": "sweden",
    "malmö": "sweden", "uppsala": "sweden", "lund": "sweden", "trondheim": "norway",
    "bergen": "norway", "espoo": "finland", "tampere": "finland", "oulu": "finland",
    "gdansk": "poland", "poznan": "poland", "lodz": "poland", "katowice": "poland",
    "bratislava": "slovakia", "ljubljana": "slovenia", "zagreb": "croatia",
    "belgrade": "serbia", "novi sad": "serbia", "kyiv": "ukraine", "lviv": "ukraine",
    "kharkiv": "ukraine", "iasi": "romania", "timisoara": "romania",
    "thessaloniki": "greece", "nicosia": "cyprus", "limassol": "cyprus",
    "valletta": "malta", "luxembourg city": "luxembourg", "reykjavik": "iceland",
    "graz": "austria", "linz": "austria", "lausanne": "switzerland", "bern": "switzerland",
    "bologna": "italy", "florence": "italy", "naples": "italy", "seville": "spain",
    "malaga": "spain", "bilbao": "spain", "marseille": "france", "nice": "france",
    "nantes": "france", "bordeaux": "france", "lille": "france", "grenoble": "france",
    "sophia antipolis": "france", "glasgow": "uk", "belfast": "uk", "birmingham": "uk",
    "nottingham": "uk", "sheffield": "uk", "newcastle": "uk", "reading": "uk",
    "brighton": "uk", "galway": "ireland", "limerick": "ireland", "dresden": "germany",
    "leipzig": "germany", "heidelberg": "germany", "karlsruhe": "germany",
    "darmstadt": "germany", "aachen": "germany", "tübingen": "germany",
    "tubingen": "germany", "nuremberg": "germany",
    "istanbul": "turkey", "ankara": "turkey", "izmir": "turkey",
}

COUNTRIES = {
    "uk", "united kingdom", "great britain", "england", "scotland", "wales",
    "ireland", "germany", "deutschland", "france", "spain", "portugal",
    "netherlands", "the netherlands", "holland", "belgium", "luxembourg",
    "sweden", "denmark", "norway", "finland", "iceland", "poland", "czechia",
    "czech republic", "slovakia", "austria", "switzerland", "italy", "greece",
    "romania", "bulgaria", "hungary", "croatia", "slovenia", "serbia",
    "estonia", "latvia", "lithuania", "ukraine", "turkey", "türkiye", "cyprus", "malta",
    "bosnia and herzegovina", "bosnia", "albania", "north macedonia", "montenegro",
    "moldova", "kosovo", "liechtenstein", "monaco", "andorra", "belarus",
    "hong kong", "taiwan", "korea", "republic of korea", "brunei", "cambodia",
    "usa", "u.s.", "u.s.a.", "us", "united states", "united states of america",
    "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru",
    "uruguay", "costa rica", "india", "pakistan", "bangladesh", "sri lanka",
    "china", "japan", "south korea", "singapore", "malaysia", "indonesia",
    "philippines", "vietnam", "thailand", "australia", "new zealand",
    "israel", "uae", "united arab emirates", "saudi arabia", "ksa", "qatar",
    "kuwait", "bahrain", "oman", "jordan", "lebanon", "egypt",
    "south africa", "nigeria", "kenya", "morocco", "ghana",
}

# --- the regions the dashboard is organised into ----------------------------
#
# These decide which tab a posting lands in, so they are kept as explicit sets
# rather than derived from anything: a company in Dubai and a company in Berlin
# are different propositions and the difference should not depend on a guess.

GULF = {"uae", "united arab emirates", "saudi arabia", "ksa", "qatar",
        "kuwait", "bahrain", "oman"}

EUROPE = {
    "uk", "united kingdom", "great britain", "england", "scotland", "wales",
    "ireland", "germany", "deutschland", "france", "spain", "portugal",
    "netherlands", "the netherlands", "holland", "belgium", "luxembourg",
    "sweden", "denmark", "norway", "finland", "iceland", "poland", "czechia",
    "czech republic", "slovakia", "austria", "switzerland", "italy", "greece",
    "romania", "bulgaria", "hungary", "croatia", "slovenia", "serbia",
    "estonia", "latvia", "lithuania", "ukraine", "cyprus", "malta",
    "turkey", "türkiye", "bosnia and herzegovina", "bosnia", "albania", "north macedonia",
    "montenegro", "moldova", "kosovo", "liechtenstein", "monaco", "andorra", "belarus",
}

PAKISTAN = {"pakistan"}

# East and Southeast Asia: China, Singapore, Malaysia and their neighbours. Employer-sponsored
# work passes are the normal route here, as in the Gulf, so silence about a visa is not a no.
ASIA = {"china", "hong kong", "taiwan", "japan", "south korea", "korea", "republic of korea",
        "singapore", "malaysia", "indonesia", "thailand", "vietnam", "philippines", "brunei",
        "cambodia"}

# Asked to be left out. A posting whose only places are these is dropped; one that also names
# a target country, or is open worldwide, is kept.
EXCLUDED = {"india", "bangladesh"}

# One display name per country, whatever spelling the posting used.
CANONICAL = {
    "uk": "United Kingdom", "united kingdom": "United Kingdom",
    "great britain": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom", "deutschland": "Germany",
    "the netherlands": "Netherlands", "holland": "Netherlands", "czech republic": "Czechia",
    "türkiye": "Turkey", "bosnia": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina", "north macedonia": "North Macedonia",
    "uae": "United Arab Emirates", "united arab emirates": "United Arab Emirates",
    "ksa": "Saudi Arabia", "saudi arabia": "Saudi Arabia", "korea": "South Korea",
    "republic of korea": "South Korea", "south korea": "South Korea",
    "hong kong": "Hong Kong", "usa": "United States", "u.s.": "United States",
    "u.s.a.": "United States", "us": "United States", "united states": "United States",
    "united states of america": "United States", "new zealand": "New Zealand",
    "sri lanka": "Sri Lanka", "south africa": "South Africa", "costa rica": "Costa Rica",
}


def canonical(country: str) -> str:
    return CANONICAL.get(country, country.title())


def countries_of(location: str) -> list[str]:
    """Every country a location string names, by display name, in a stable order."""
    found: set[str] = set()
    for token in tokens(location):
        if token in _FILLER:
            continue
        country = token if token in COUNTRIES else CITY_COUNTRY.get(token)
        if country:
            found.add(canonical(country))
    return sorted(found)


def region_of_country(name: str) -> str:
    """The dashboard region of a country given by its display name."""
    keys = {k for k, v in CANONICAL.items() if v == name} | {name.lower()}
    if keys & GULF:
        return R_GULF
    if keys & EUROPE:
        return R_EUROPE
    if keys & PAKISTAN:
        return R_PAKISTAN
    if keys & ASIA:
        return R_ASIA
    if keys & EXCLUDED:
        return R_EXCLUDED
    return R_OTHER

# Region names used as dashboard sections.
R_GULF, R_EUROPE, R_PAKISTAN, R_OTHER = "gulf", "europe", "pakistan", "other"
R_ASIA, R_EXCLUDED = "asia", "excluded"

_REGION_WORDS = {
    "gcc": R_GULF, "middle east": R_GULF, "mena": R_GULF,
    "apac": R_ASIA, "asia pacific": R_ASIA, "southeast asia": R_ASIA,
    "asean": R_ASIA, "greater china": R_ASIA,
    "eu": R_EUROPE, "eea": R_EUROPE, "europe": R_EUROPE,
    "european union": R_EUROPE, "european economic area": R_EUROPE,
    "emea": R_EUROPE, "nordics": R_EUROPE, "benelux": R_EUROPE, "dach": R_EUROPE,
    "uk & eu": R_EUROPE,
}


def regions_of(location: str) -> set[str]:
    """Which dashboard regions a location touches. May be empty, may be several.

    A posting listing "Dubai, London" belongs in both the Gulf and the Europe
    tab: it is genuinely two opportunities, and picking one would hide the
    other. EMEA counts as Europe only — it nominally covers the Gulf too, but
    a company writing EMEA almost always means a European office.
    """
    found: set[str] = set()
    for token in tokens(location):
        if token in _FILLER:
            continue
        if token in _REGION_WORDS:
            found.add(_REGION_WORDS[token])
            continue
        country = token if token in COUNTRIES else CITY_COUNTRY.get(token)
        if not country:
            continue
        if country in GULF:
            found.add(R_GULF)
        elif country in EUROPE:
            found.add(R_EUROPE)
        elif country in PAKISTAN:
            found.add(R_PAKISTAN)
        elif country in ASIA:
            found.add(R_ASIA)
        elif country in EXCLUDED:
            found.add(R_EXCLUDED)
        else:
            found.add(R_OTHER)
    return found

REGIONS = {
    "eu", "eea", "europe", "european union", "european economic area",
    "emea", "apac", "latam", "americas", "north america", "south america",
    "asia", "africa", "middle east", "nordics", "benelux", "dach", "uk & eu",
}

GLOBAL_WORDS = {
    "anywhere", "worldwide", "global", "remote worldwide", "anywhere in the world",
    "work from anywhere", "fully remote", "global remote", "any location",
    "everywhere", "remote everywhere", "remote anywhere",
}

# Words that carry no location information and must not count either way.
_FILLER = {
    "remote", "hybrid", "onsite", "on-site", "office", "flexible", "or",
    "and", "other", "optional", "based", "home", "wfh", "various", "multiple",
    "locations", "location", "eu remote", "remote eu", "n/a", "", "-",
}

# A spaced hyphen separates as surely as a comma — "Remote - EU" is the same
# statement as "Remote, EU" — but an unspaced one is part of a name, so
# "Guinea-Bissau" and "on-site" must survive intact.
_SPLIT = re.compile(r"\s*(?:,|/|\||;|&|\bor\b|\band\b|·|—|–|\s-\s)\s*")
_PARENS = re.compile(r"\(([^)]*)\)")


# "City, ST" is the US way of writing a place, and it has to be read before the
# city is looked up: "Cambridge, MA" is Massachusetts, not the UK, and it put
# a US biotech role in the Europe tab. The two-letter code is only trusted
# directly after a comma-separated name, where nothing else uses one.
_US_STATES = ["al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc"]
_CITY_STATE = re.compile(rf"\b([a-z][a-z .'-]*?),\s*(?:{'|'.join(_US_STATES)})\b(?!\s*[a-z])")
# Cities that exist on both sides of the Atlantic. Any other city this module
# already knows keeps its country, so "Berlin, DE" stays in Germany rather
# than moving to Delaware.
_TWIN_CITIES = {"cambridge", "manchester", "birmingham", "athens", "paris", "dublin"}


def _city_state(match: re.Match) -> str:
    city = match.group(1).strip()
    known = CITY_COUNTRY.get(city)
    if known and known != "usa" and city not in _TWIN_CITIES:
        return match.group(0)
    return "usa"
_US_STATE_NAMES = re.compile(
    r"\b(?:california|massachusetts|texas|colorado|illinois|oregon|pennsylvania|"
    r"new jersey|north carolina|virginia|florida|minnesota|michigan|ohio|utah|"
    r"arizona|maryland|connecticut|tennessee|missouri|wisconsin)\b")


_WORKDAY_US = re.compile(rf"\bus-(?:{'|'.join(_US_STATES)})-")


def tokens(location: str) -> list[str]:
    """Split a location string into comparable place tokens.

    A parenthetical is pulled out first and treated as its own token, because
    "Remote (UK)" is the commonest way a country restriction is written and
    the parentheses would otherwise glue it to the word 'remote'.
    """
    text = (location or "").strip().lower()
    if not text:
        return []
    # Workday's "US-CA-Menlo Park" / "US-WA-Bellevue".
    text = _WORKDAY_US.sub("usa, ", text)
    text = _CITY_STATE.sub(_city_state, text)
    text = _US_STATE_NAMES.sub("usa", text)
    inner = _PARENS.findall(text)
    text = _PARENS.sub(" ", text)
    parts = _SPLIT.split(text) + [p for chunk in inner for p in _SPLIT.split(chunk)]
    return [_trim(p) for p in parts if _trim(p)]


# "Paris office", "London HQ", "Berlin area" all name a place and then say
# something about the building. Left attached, the token matches nothing and
# the whole string is reported unknown — which sent a Paris-only role down the
# prose path and had it classified as region-wide.
_QUALIFIER = re.compile(
    r"\b(?:office|offices|hq|headquarters|area|metro|region|based|hub|site|"
    r"campus|centre|center|branch|studio)\b"
)


def _trim(part: str) -> str:
    return _QUALIFIER.sub(" ", part).strip(" .()-,*").strip()


def classify(location: str) -> tuple[str, str]:
    """(scope, reason). UNKNOWN when the string cannot be read confidently."""
    parts = tokens(location)
    if not parts:
        return UNKNOWN, "no location given"

    countries: set[str] = set()
    regions: set[str] = set()
    unknown: list[str] = []

    for token in parts:
        if token in _FILLER:
            continue
        if token in GLOBAL_WORDS:
            return GLOBAL, f"location says {token!r}"
        if token in REGIONS:
            regions.add(token)
        elif token in COUNTRIES:
            countries.add(token)
        elif token in CITY_COUNTRY:
            countries.add(CITY_COUNTRY[token])
        else:
            unknown.append(token)

    # Fail closed. An unreadable token means this function does not know, and
    # saying so sends the caller to the prose patterns instead of handing it a
    # confident answer built on a gap in a word list.
    if unknown and not (countries or regions):
        return UNKNOWN, f"unrecognised location: {', '.join(unknown[:3])}"

    if regions:
        return REGION, f"location names region(s): {', '.join(sorted(regions))}"
    if len(countries) == 1:
        return COUNTRY, f"location is {next(iter(countries))} only"
    if countries:
        # Several named countries is still a closed list, not open hiring.
        return COUNTRY, f"location lists only: {', '.join(sorted(countries))}"
    return UNKNOWN, "no place recognised"
