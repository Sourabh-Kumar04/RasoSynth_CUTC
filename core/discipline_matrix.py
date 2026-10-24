"""Universal Discipline Incompatibility Matrix & Polysemy Disambiguation Engine.

Solves cross-discipline homonym collisions (e.g. GST = Glutathione S-Transferase vs
Goods & Services Tax, Rust = plant fungus vs programming language, Pandas = giant panda
vs dataframe library) across discovery, filtering, and dataset construction.
"""
from enum import Enum
import re
from typing import Optional, Tuple, List, Dict, Set, Any


class Discipline(str, Enum):
    SOFTWARE_AI = "software_ai"
    LAW_TAX = "law_tax"
    BIOMEDICAL = "biomedical"
    FINANCE_ECONOMICS = "finance_economics"
    NATURAL_SCIENCES = "natural_sciences"
    HUMANITIES = "humanities"
    GENERAL = "general"


# Keywords indicating broad disciplines
_DISCIPLINE_INDICATORS: Dict[Discipline, Set[str]] = {
    Discipline.SOFTWARE_AI: {
        "software", "programming", "code", "coding", "python", "javascript", "typescript",
        "rust", "golang", "c++", "java", "machine learning", "deep learning", "ai", "llm",
        "nlp", "computer vision", "neural network", "transformer", "sft", "rlhf", "dataset",
        "algorithm", "api", "backend", "frontend", "database", "sql", "linux", "git",
        "docker", "kubernetes", "async", "compiler", "framework", "library", "microservice"
    },
    Discipline.LAW_TAX: {
        "tax", "taxation", "law", "legal", "statute", "gst", "vat", "statutory", "compliance",
        "audit", "treaty", "court", "tribunal", "appellate", "ruling", "judge", "jurisdiction",
        "act", "section", "cgst", "sgst", "igst", "itat", "irs", "hmrc", "corporate law",
        "indirect tax", "direct tax", "income tax", "tds", "tcs", "customs duty", "excise"
    },
    Discipline.BIOMEDICAL: {
        "medicine", "medical", "clinical", "biomedical", "disease", "patient", "cellular",
        "molecular", "genetics", "gene", "protein", "enzyme", "pharmacology", "oncology",
        "pathology", "surgery", "hospital", "radiology", "ct scan", "mri", "biochemistry"
    },
    Discipline.FINANCE_ECONOMICS: {
        "finance", "financial", "economics", "economy", "banking", "stock", "equity",
        "portfolio", "trading", "investment", "credit", "macroeconomics", "monetary",
        "capital market", "securities", "bond", "forex", "derivative"
    },
    Discipline.NATURAL_SCIENCES: {
        "physics", "astronomy", "geology", "chemistry", "climate", "ecology", "botany",
        "agriculture", "crop", "geological", "meteorology", "atmospheric", "oceanography"
    },
}

# Polysemous terms with discipline-specific collisions and search query anchors
_POLYSEMY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "rust": {
        Discipline.SOFTWARE_AI: {
            "anchor": "rust programming language",
            "forbidden": [
                "puccinia", "wheat rust", "crop disease", "fungal spores", "plant pathology",
                "foliar", "agronomy", "iron oxide", "corrosion of steel", "rust fungus",
                "fungicide", "metallurgy", "alloy oxidation", "rust infected"
            ]
        },
        Discipline.NATURAL_SCIENCES: {
            "anchor": "wheat rust plant pathology",
            "forbidden": ["cargo", "tokio", "async fn", "borrow checker", "serde", "compiler", "crates.io"]
        }
    },
    "pandas": {
        Discipline.SOFTWARE_AI: {
            "anchor": "python pandas dataframe library",
            "forbidden": [
                "ailuropoda", "melanoleuca", "giant panda", "bamboo forest", "zoological",
                "panda bear", "wildlife sanctuary", "panda cub", "mammal", "endangered bear"
            ]
        }
    },
    "go": {
        Discipline.SOFTWARE_AI: {
            "anchor": "golang go programming language",
            "forbidden": [
                "board game", "weiqi", "baduk", "igo stones", "joseki", "handicap stones", "dan rank"
            ]
        }
    },
    "swift": {
        Discipline.SOFTWARE_AI: {
            "anchor": "apple swift ios programming",
            "forbidden": [
                "jonathan swift", "gulliver", "satire", "apus apus", "swallow bird", "ornithology",
                "avian flight", "plumage"
            ]
        }
    },
    "transformer": {
        Discipline.SOFTWARE_AI: {
            "anchor": "deep learning transformer attention model",
            "forbidden": [
                "substation", "high voltage", "electromagnetic induction", "transformer winding",
                "transformer oil", "core loss", "primary winding", "secondary winding", "electrical grid",
                "step-up transformer", "step-down transformer", "power transformer"
            ]
        }
    },
    "transformers": {
        Discipline.SOFTWARE_AI: {
            "anchor": "deep learning transformer attention model",
            "forbidden": [
                "substation", "high voltage", "electromagnetic induction", "transformer winding",
                "transformer oil", "core loss", "primary winding", "secondary winding", "electrical grid"
            ]
        }
    },
    "bert": {
        Discipline.SOFTWARE_AI: {
            "anchor": "bert language model nlp",
            "forbidden": ["sesame street", "ernie and bert", "muppet"]
        }
    },
    "llama": {
        Discipline.SOFTWARE_AI: {
            "anchor": "meta llama open source llm",
            "forbidden": [
                "lama glama", "camelid", "fleece", "wool fiber", "andes mountains", "peru livestock",
                "alpaca and llama", "camelidae"
            ]
        }
    },
    "can": {
        Discipline.SOFTWARE_AI: {
            "anchor": "controller area network can bus automotive",
            "forbidden": [
                "tin can", "beverage can", "canned food", "canning process", "aluminum can recycling"
            ]
        }
    },
    "cat": {
        Discipline.BIOMEDICAL: {
            "anchor": "computed tomography cat scan radiology",
            "forbidden": [
                "feline", "kitten", "domestic cat", "cat food", "whiskers", "claws", "veterinary feline"
            ]
        }
    },
    "tree": {
        Discipline.SOFTWARE_AI: {
            "anchor": "decision tree search algorithm cs",
            "forbidden": [
                "timber", "forestry", "deforestation", "tree canopy", "arboriculture", "sapling",
                "pine tree", "oak tree", "foliage", "bark"
            ]
        }
    },
    "forest": {
        Discipline.SOFTWARE_AI: {
            "anchor": "random forest machine learning ensemble",
            "forbidden": [
                "timber", "forestry", "deforestation", "rainforest ecology", "national forest", "woodland"
            ]
        }
    },
    "mining": {
        Discipline.SOFTWARE_AI: {
            "anchor": "data mining pattern recognition",
            "forbidden": [
                "coal mining", "gold mining", "ore extraction", "underground mine", "shaft",
                "mineral extraction", "quarrying", "mine tailing", "subterranean excavation"
            ]
        }
    },
    "pipeline": {
        Discipline.SOFTWARE_AI: {
            "anchor": "data engineering pipeline etl",
            "forbidden": [
                "crude oil pipeline", "natural gas pipeline", "petroleum pipeline", "oil transport",
                "gas transmission", "pipeline leak crude", "pipeline construction oil"
            ]
        }
    },
    "gst": {
        Discipline.LAW_TAX: {
            "anchor": "goods and services tax law compliance",
            "forbidden": [
                "glutathione", "s-transferase", "nrf2", "enzyme", "oxidative stress",
                "polymorphism", "cancer susceptibility", "cellular detoxification",
                "biochemical assay", "molecular docking", "xenobiotic"
            ]
        },
        Discipline.BIOMEDICAL: {
            "anchor": "glutathione s-transferase enzyme",
            "forbidden": [
                "goods and services tax", "input tax credit", "cgst", "sgst", "igst", "tax invoice",
                "gstr", "indirect tax", "taxpayer"
            ]
        }
    },
    "sec": {
        Discipline.LAW_TAX: {
            "anchor": "us securities and exchange commission sec filing",
            "forbidden": [
                "southeastern conference", "college football", "ncaa football", "touchdowns",
                "quarterback", "sec championship game", "alabama crimson", "georgia bulldogs"
            ]
        },
        Discipline.FINANCE_ECONOMICS: {
            "anchor": "sec 10-k financial filing regulatory",
            "forbidden": [
                "southeastern conference", "college football", "ncaa football", "touchdowns",
                "quarterback", "sec championship game"
            ]
        }
    }
}

# Cross-discipline broad collision indicators
_DISCIPLINE_COLLISIONS: Dict[Discipline, List[str]] = {
    Discipline.SOFTWARE_AI: [
        "phytopathology", "puccinia", "crop yield", "wheat rust", "botany", "plant disease",
        "agronomy", "veterinary", "feline", "surgical resection", "chemotherapy", "cardiology",
        "ore mining", "quarrying", "underground shaft", "crude petroleum", "transformer oil"
    ],
    Discipline.LAW_TAX: [
        "glutathione", "s-transferase", "nrf2", "molecular dynamics", "quantum mechanics",
        "astrophysics", "stellar", "galaxy cluster", "biochemical assay", "in vitro",
        "in vivo", "oncology prognosis", "arteriovenous fistula", "hemelb"
    ],
    Discipline.BIOMEDICAL: [
        "tax audit", "input tax credit", "cgst", "sgst", "statutory tax filing", "real estate agent",
        "automotive repair", "video game cheat"
    ],
    Discipline.FINANCE_ECONOMICS: [
        "touchdowns", "quarterback", "championship trophy", "bracketology", "sports fantasy"
    ]
}


def detect_discipline(domain: str, raw_input: str = "") -> Discipline:
    """Classify the dominant discipline from domain string and raw user prompt."""
    combined = f"{str(domain).lower()} {str(raw_input).lower()}"

    # Score matches per discipline
    scores: Dict[Discipline, int] = {d: 0 for d in Discipline}
    for disc, kw_set in _DISCIPLINE_INDICATORS.items():
        for kw in kw_set:
            if kw in combined:
                scores[disc] += 2 if len(kw.split()) > 1 else 1

    # Special law / tax boosted check
    if any(k in combined for k in ["tax", "gst", "vat", "cgst", "statute", "tribunal", "itat", "audit"]):
        scores[Discipline.LAW_TAX] += 5

    # Software / AI boosted check
    if any(k in combined for k in ["dataset", "sft", "rlhf", "model", "python", "code", "neural", "benchmark"]):
        scores[Discipline.SOFTWARE_AI] += 3

    best_disc = max(scores, key=lambda k: scores[k])
    return best_disc if scores[best_disc] > 0 else Discipline.GENERAL


def get_polysemy_anti_domains(domain: str, raw_input: str = "") -> List[str]:
    """Extract applicable anti-domains for polysemous terms and jurisdiction constraints."""
    discipline = detect_discipline(domain, raw_input)
    combined = f"{str(domain).lower()} {str(raw_input).lower()}"
    anti_domains: List[str] = []

    # 1. Polysemy term checks
    tokens = set(re.findall(r'\b[a-z0-9_-]+\b', combined))
    for term, disc_map in _POLYSEMY_REGISTRY.items():
        if term in tokens or term in combined:
            if discipline in disc_map:
                anti_domains.extend(disc_map[discipline].get("forbidden", []))

    # 2. Jurisdictional isolation for tax/legal queries
    if discipline == Discipline.LAW_TAX:
        is_indian = any(k in combined for k in ["indian", "india", "cgst", "sgst", "igst", "itat", "gstr", "cbic", "cbdt", "16(4)", "194q"])
        if is_indian:
            anti_domains.extend([
                "uzbekistan", "uzbek", "united states", "internal revenue service", "irs ",
                "subpart rr", "45q", "australia", "australian", "hmrc", "iras", "singapore tax",
                "south africa", "canadian tax", "republic of uzbekistan"
            ])
        is_us = any(k in combined for k in ["united states", "u.s.", "irs", "internal revenue", "treasury regulation"])
        if is_us and not is_indian:
            anti_domains.extend(["cgst", "sgst", "igst", "itat", "cbic", "cbdt", "gstr-3b"])

    # Deduplicate and return
    return list(dict.fromkeys([a.lower().strip() for a in anti_domains if a.strip()]))


def anchor_query(query: str, domain: str, raw_input: str = "") -> str:
    """Disambiguate short or ambiguous query terms with a discipline anchor."""
    discipline = detect_discipline(domain, raw_input or query)
    q_lower = query.lower().strip()
    tokens = set(re.findall(r'\b[a-z0-9_-]+\b', q_lower))

    for term, disc_map in _POLYSEMY_REGISTRY.items():
        if term in tokens:
            if discipline in disc_map:
                anchor = disc_map[discipline].get("anchor")
                if anchor:
                    # Check if the disambiguating qualifier keywords (excluding the term itself) are already present
                    qualifiers = [p for p in anchor.split() if p.lower() != term]
                    if not any(q in q_lower for q in qualifiers[:2]):
                        return f"{query} {anchor}"

    return query


def is_content_discipline_compatible(
    content: str,
    domain: str,
    raw_input: str = "",
    title: str = "",
    url: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    Verify whether content text is genuinely compatible with the detected discipline.
    Returns (True, None) if compatible, or (False, reason) if a cross-discipline collision is detected.
    """
    if not content and not title:
        return True, None

    discipline = detect_discipline(domain, raw_input)
    check_text = f"{title.lower()} {url.lower()} {content[:4000].lower()}"

    # 1. Check specific polysemy anti-domains
    anti_terms = get_polysemy_anti_domains(domain, raw_input)
    for anti in anti_terms:
        if anti in check_text:
            return False, f"cross_discipline_collision: {anti}"

    # 2. Check broad discipline collisions
    if discipline in _DISCIPLINE_COLLISIONS:
        for broad_anti in _DISCIPLINE_COLLISIONS[discipline]:
            if broad_anti in check_text:
                return False, f"broad_discipline_collision: {broad_anti}"

    return True, None
