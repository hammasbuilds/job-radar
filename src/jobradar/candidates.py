"""Employers to look for, by region: the input to `scripts/discover_boards.py`.

These are names, not boards. Nobody publishes which applicant-tracking system a company uses,
so the discovery script tries each name on every provider this tool can read and records only
the boards that answer with postings (`boards_found.json`). A name that resolves nowhere costs
a few requests and is reported, not guessed into the crawl.

Weighted to where the work is wanted - Europe, the Gulf, Pakistan, and East and Southeast Asia
- and to companies that hire ML, vision, generative and agentic AI people. India and Bangladesh
are left out on request. LinkedIn is never asked about anything.
"""

from __future__ import annotations

EUROPE = """
DeepL; Mistral AI; Aleph Alpha; Helsing; Synthesia; Wayve; PolyAI; Hugging Face; Photoroom;
Dataiku; ElevenLabs; Black Forest Labs; Stability AI; Faculty; Tractable; Cera; Isomorphic Labs;
Graphcore; Onfido; Prima; N26; Zalando; Delivery Hero; HelloFresh; Celonis; Personio; Contentful;
GetYourGuide; Klarna; Spotify; Bolt; Wolt; Revolut; Monzo; Wise; Lovable; Poolside; H Company;
LightOn; Owkin; Shift Technology; Alan; Doctolib; BlaBlaCar; Back Market; Mirakl; Qonto;
Pennylane; Swile; Ledger; Sorare; ManoMano; Vinted; Nord Security; Pipedrive; Veriff; Starship;
Sana Labs; Legora; Einride; Ericsson; King; Truecaller; Tink; Trustly; Epidemic Sound; Voi; Oda;
Kahoot; Cognite; reMarkable; Visma; Supercell; Rovio; Oura; Varjo; Silo AI; IQM; Aiven; ICEYE;
Relex; Smartly; Swappie; Corti; Pleo; Lunar; Templafy; Trustpilot; Too Good To Go; Vivino;
Siteimprove; Merantix; Parloa; Langdock; Cognigy; Konux; Twaice; Trade Republic;
Scalable Capital; Flix; Enpal; 1Komma5; Sennder; Forto; Billie; Mambu; Raisin; Solaris; Taxfix;
Staffbase; Babbel; Blinkist; SoundCloud; ResearchGate; Auto1; Quantum Systems; Isar Aerospace;
Volocopter; Agile Robots; Neura Robotics; Magazino; Wandelbots; Proxima Fusion; Marvel Fusion;
ARX Robotics; Tacto; Ory; Cosuno; Scandit; Nexthink; Climeworks; Beekeeper; Frontify; ANYbotics;
Proton; Lakera; Unique; Squirro; Adyen; Booking; Picnic; Mollie; Bunq; Bird; Backbase; Bynder;
Catawiki; Miro; Framer; Mews; Productboard; Rohlik; Kiwi; Apify; Rossum; GoodData; DocPlanner;
Booksy; Brainly; Allegro; Text; Glia; DeepMind; Darktrace; Quantexa; Cleo; Tide; GoCardless;
Thought Machine; Snyk; Multiverse; Peak; Paddle; Primer; Yapily; Zego; Zilch; Marshmallow;
Beamery; Ocado Technology; Arm; Improbable; Signal AI; Luminance; Robin AI; Conjecture;
Apollo Research; Lindus Health; Cogna; Causaly; BenevolentAI; LabGenius; Healx; CuspAI;
Basecamp Research; Latent Labs; PhysicsX; Nscale; Fractile; Lumai; Oxa; Humanloop; Unitary; V7;
Encord; Speechmatics; Seldon; Featurespace; ComplyAdvantage; Huma; Kheiron; Dust; Nabla;
Pigment; Contentsquare; Algolia; Spendesk; PayFit; Ornikar; Lydia; Agicap; Aircall; Malt;
Ivalua; Giskard; Zama; Pasqal; Alice & Bob; Exotec; Wandercraft; Glovo; Cabify; Typeform;
TravelPerk; Factorial; Wallapop; Jobandtalent; Freepik; Feedzai; Talkdesk; Unbabel;
Sword Health; OutSystems; Remote; Satispay; Scalapay; Bending Spoons; Intercom; Workhuman;
Fenergo; Flipdish; Wayflyer; Weaviate; Qdrant; Rasa; Axelera AI; 1X; Deliveroo; Depop;
Farfetch; Elastic; Canonical; JetBrains; Neo4j; Commercetools; Spryker; Grover; Raisin;
Tier; Choco; Omio; Clark; Wefox; Zenjob; Camunda; Tomtom; MessageBird; Sendcloud; Otrium;
Bitvavo; Everphone; Supermetrics; Hopin; Paysend; Kraken; Bitpanda; GoStudent; Tourlane;
Moonfare; Mobimeo; Lilium; Dryad; Planet A Foods; Fernride; Arculus; Sereact; Robco;
Quantagonia; Nyonic; Cradle; Dataloop; Lindera; Ada Health; Kry; Livi; Doctolib; Mindler;
Instabee; Kognity; Sana; Hemnet; Klarna; Northvolt; Volvo Cars; Polestar; Zenseact; Embark;
Mojang; Paradox Interactive; Unity; Tobii; Axis Communications; Spotify; Detectify; Hedvig;
Lendo; Tibber; Kolonial; Vipps; Schibsted; Telenor; Yara; Equinor; Aker BP; DNB; Nordnet;
Wolt; Maria; Varjo; Rovio; Smartly; Nokia; Reaktor; Futurice; Vincit; Sievo; Oura; Kahoot
"""

GULF = """
Careem; Tabby; Tamara; Noon; G42; Presight; Core42; Inception; MBZUAI;
Technology Innovation Institute; Lean Technologies; Foodics; Salla; Zid; Unifonic; Sary; Ninja;
Jahez; Mozn; Lucidya; Nana; Kitopi; Talabat; Property Finder; Bayut; Dubizzle; Anghami; Swvl;
Pure Harvest; Sarwa; Baraka; Yalla; Qlub; Rain; BitOasis; Huspy; Stake; Ziina; XPANCEO;
Bayanat; Space42; Humain; Elm; Hala; Lean; Tarabut; Telda; Brightskies; Instabug; Halan;
MaxAB; Breadfast; Vezeeta; Paymob; Fawry; Thndr; Khazna; Rabbit; Aqar; Nymcard; Wio; Mashreq;
Emirates NBD; Majid Al Futtaim; Chalhoub; Aramex; Deliveroo UAE; Seez; Calo; Floward; Mumzworld
"""

PAKISTAN = """
Arbisoft; Systems Limited; NetSol; 10Pearls; Afiniti; Tkxel; Folio3; Securiti; Motive; Educative;
Tajir; Bazaar; Airlift; SadaPay; NayaPay; Abhi; Bykea; Zameen; Daraz; Jazz; VentureDive; Emumba;
Xgrid; Confiz; Contour Software; Cubix; Techlogix; i2c; Ebryx; Arpatech; TRG; Retailo; Dastgyr;
Jugnu; Finja; Oraan; Trukkr; Krave Mart; PostEx; Truck It In; Codeninja; Tintash; Datics;
Visionet; Gaditek; Rapid Compute; Mindstorm Studios; Zones; Ibex; Devsinc; PureLogics; Cogent Labs;
Hashmove; Sastaticket; Bookme; Haball; Tapmad; Markaz; Neem; Safepay; Keenu; Zindigi; Easypaisa;
Telenor Microfinance Bank; Teradata Pakistan; Ciklum; Turing Pakistan; Red Buffer; Antematter;
Fiverr Pakistan; Upwork Pakistan; Wateen; Nayatel; PTCL; K-Electric; Engro; Lucky Group
"""

ASIA = """
Grab; Sea; Shopee; Garena; Lazada; ShopBack; Carousell; Ninja Van; PropertyGuru;
Advance Intelligence; Trax; ViSenze; Biofourmis; AI Singapore; Taiger; Xendit; Nium; Thunes;
Aspire; Funding Societies; StashAway; Endowus; Coda Payments; 2C2P; Airwallex; Rapyd; Patsnap;
Carsome; Aerodyne; Fave; Boost; Touch n Go; Capital A; GoTo; Gojek; Tokopedia; Traveloka;
Ruangguru; Bukalapak; Kredivo; VNG; MoMo; Tiki; Trusting Social; Mynt; Maya; Kumu; Agoda;
LINE MAN Wongnai; Ascend Money; Klook; Lalamove; WeLab; ZA Bank; Appier; Gogoro; Pinkoi; KKday;
SenseTime; MiniMax; Shein; Sakana AI; Preferred Networks; Mercari; SmartNews; LINE Yahoo;
Woven by Toyota; Money Forward; Ubie; PKSHA; ELYZA; Paidy; Sansan; Tier IV; Ascent Robotics;
Upstage; Naver; Kakao; Coupang; Toss; Rebellions; FuriosaAI; Twelve Labs; Riiid; Krafton;
Sendbird; Hyperconnect; Lunit; Vuno; Moloco; Dable; Hyundai Motor Group; Samsung Research;
Sony AI; Rakuten; DeNA; CyberAgent; Nulab; Wantedly; Rapyuta Robotics; Mujin; Telexistence;
Hinge Health Asia; Doctor Anywhere; Halodoc; Alodokter; Qoo10; Zalora; Foodpanda; Shopline;
Zilingo; Glints; Kopi Kenangan; Akulaku; Pomelo; Wego; 99.co; Ohmyhome; Homage; Hmlet; Ryde;
Tada; Gogovan; Ninja Logistics; Mobile Premier League; Accredify; Sleek; Osome; Tazapay; YouTrip
"""

GLOBAL_AI = """
OpenAI; Anthropic; Google DeepMind; Cohere; AI21 Labs; Perplexity; Scale AI; Databricks;
Snowflake; Character AI; Runway; Pika; Together AI; Fireworks AI; Modal; Replicate;
Weights & Biases; Pinecone; Chroma; LangChain; LlamaIndex; Anysphere; Cognition; Sierra; Harvey;
Glean; Hebbia; Writer; Jasper; Cresta; Decagon; Deepgram; AssemblyAI; Rev; Descript; Luma AI;
Genmo; Suno; Contextual AI; Reka; Magic; Adept; xAI; Physical Intelligence; Figure; Covariant;
Skild AI; Tenstorrent; Groq; Cerebras; SambaNova; Lightmatter; Etched; d-Matrix; Hailo;
Hugging Face; Mistral; Stability; Nomic; Ollama; Anyscale; Lambda; CoreWeave; Crusoe; Vercel;
Supabase; Neon; PostHog; Sentry; Grafana Labs; Temporal; Pydantic; Hex; Mozilla; Wikimedia;
Mercor; Scale; Eleuther AI; Apollo; Redwood Research; FAR AI; METR; Epoch AI; Goodfire;
Transluce; Imbue; Liquid AI; Sakana; Elicit; Ought; Cartesia; Hume AI; Inflection AI; Mosaic
"""

# The AI training and expert-work platforms: contract and small-contract work grading, writing
# and checking model output. Most post on their own sites; the ones on a readable ATS are found
# by the same probe and their roles flow into the normal crawl.
AI_WORK_PLATFORMS = """
Mercor; DataAnnotation; Alignerr; Labelbox; micro1; AfterQuery; Datacurve; Shipd; Outlier;
Remotasks; Turing; Toloka; Mindrift; Prolific; Invisible Technologies; Surge AI; Handshake;
Snorkel AI; Appen; TELUS Digital; Sama; CloudFactory; iMerit; SuperAnnotate; Kili Technology;
HumanSignal; Pareto; Revelo; G2i; Andela; Toptal; Arc; Braintrust; Deccan AI; Soul AI;
Rex; Abaka AI; Mindtech; Centaur Labs; Gloss; Stellar; Cohere Labs; Turing Enterprises
"""

REGIONS = {
    "europe": EUROPE, "gulf": GULF, "pakistan": PAKISTAN, "asia": ASIA, "global": GLOBAL_AI,
    "ai-work": AI_WORK_PLATFORMS,
}


def names(region: str | None = None) -> list[tuple[str, str]]:
    """[(region, company name)], de-duplicated, in a stable order."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for key, block in REGIONS.items():
        if region and key != region:
            continue
        for raw in block.replace("\n", " ").split(";"):
            name = " ".join(raw.split())
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append((key, name))
    return out


def slugs_for(name: str) -> list[str]:
    """The spellings a company's board slug is usually written in."""
    low = name.lower().replace("&", "and").replace("+", "plus")
    words = [w for w in "".join(c if c.isalnum() or c == " " else " " for c in low).split()]
    if not words:
        return []
    joined = "".join(words)
    out = [joined]
    if len(words) > 1:
        out.append("-".join(words))
    for suffix in (" ai", " labs", " technologies", " limited", " group"):
        if low.endswith(suffix) and len(words) > 1:
            out.append("".join(words[:-1]))
    return list(dict.fromkeys(out))
