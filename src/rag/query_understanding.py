import re
import unicodedata
from dataclasses import dataclass
from typing import Any


INTENT_CAMARAS = "camaras"
INTENT_INCIDENCIAS = "incidencias"
INTENT_CONGESTION = "congestion"
INTENT_OBRAS_CORTES = "obras_cortes"
INTENT_CORPUS = "corpus_multifuente"
INTENT_GENERAL = "general"

ROAD_PATTERN = re.compile(
    r"\b(?:AP|A|BI|GI|N)-\s*\d+[A-Z]?\b",
    flags=re.IGNORECASE,
)

SOURCE_ALIASES = {
    "trafikoa": "Trafikoa",
    "trafico euskadi": "Trafikoa",
    "gobierno vasco": "Trafikoa",
    "ayuntamiento": "Ayuntamiento de Bilbao",
    "ayuntamiento de bilbao": "Ayuntamiento de Bilbao",
    "bilbao.eus": "Ayuntamiento de Bilbao",
    "deia": "DEIA - Bizkaimove",
    "bizkaimove": "DEIA - Bizkaimove",
    "bluesky": "Bluesky",
}

CAMERA_TERMS = {
    "camara",
    "camaras",
    "camera",
    "cameras",
    "cctv",
    "webcam",
    "imagen",
    "imagenes",
}
CONGESTION_TERMS = {
    "congestion",
    "congestiones",
    "atasco",
    "atascos",
    "retencion",
    "retenciones",
    "trafico lento",
    "trafico denso",
    "densidad",
}
OBRAS_CORTES_TERMS = {
    "obra",
    "obras",
    "corte",
    "cortes",
    "cortado",
    "cortada",
    "cortados",
    "cortadas",
    "carril cortado",
    "sentido cortado",
    "paso alternativo",
    "ocupacion",
    "desvio",
    "desvios",
}
INCIDENCIA_TERMS = {
    "incidencia",
    "incidencias",
    "accidente",
    "accidentes",
    "averia",
    "averias",
    "obstaculo",
    "obstaculos",
    "puerto",
    "puertos",
}
CORPUS_TERMS = {
    "aviso",
    "avisos",
    "noticia",
    "noticias",
    "publicacion",
    "publicaciones",
    "post",
    "posts",
    "fuente",
    "fuentes",
}

STOPWORDS = {
    "a",
    "al",
    "alguna",
    "algun",
    "alguno",
    "ante",
    "cerca",
    "como",
    "con",
    "cual",
    "cuales",
    "cuando",
    "de",
    "del",
    "desde",
    "donde",
    "el",
    "en",
    "entre",
    "es",
    "esa",
    "ese",
    "esta",
    "estan",
    "este",
    "hay",
    "hacia",
    "hasta",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "muestrame",
    "muestra",
    "mostrar",
    "para",
    "parece",
    "por",
    "pregunta",
    "que",
    "quiero",
    "ruta",
    "se",
    "si",
    "sobre",
    "tiene",
    "tienen",
    "un",
    "una",
    "via",
    "vía",
    "y",
}

PLACE_STOPWORDS = STOPWORDS | CAMERA_TERMS | CONGESTION_TERMS | OBRAS_CORTES_TERMS | INCIDENCIA_TERMS | CORPUS_TERMS

KNOWN_PLACE_ALIASES = {
    "alameda recalde": "Alameda Recalde",
    "bilbao": "Bilbao",
    "lekeitio": "Lekeitio",
    "amoroto": "Amoroto",
    "sondika": "Sondika",
    "mallabia": "Mallabia",
    "ermua": "Ermua",
    "galdakao": "Galdakao",
    "barakaldo": "Barakaldo",
    "getxo": "Getxo",
    "basauri": "Basauri",
    "durango": "Durango",
    "gernika": "Gernika",
    "bermeo": "Bermeo",
    "mungia": "Mungia",
    "portugalete": "Portugalete",
    "santurtzi": "Santurtzi",
    "leioa": "Leioa",
    "erandio": "Erandio",
    "zalla": "Zalla",
    "balmaseda": "Balmaseda",
    "vitoria": "Vitoria-Gasteiz",
    "gasteiz": "Vitoria-Gasteiz",
    "donostia": "Donostia",
    "san sebastian": "San Sebastian",
    "irun": "Irun",
    "eibar": "Eibar",
    "ondarroa": "Ondarroa",
    "markina": "Markina-Xemein",
    "moyua": "Moyua",
    "heros": "Heros",
    "mazarredo": "Alameda Mazarredo",
    "san francisco": "San Francisco",
    "tiboli": "Tiboli",
    "txotena": "Txotena",
    "henao": "Henao",
}


@dataclass(frozen=True)
class QueryUnderstanding:
    raw_query: str
    intent: str
    lugares: list[str]
    carreteras: list[str]
    is_route: bool = False
    route_from: str | None = None
    route_to: str | None = None
    source_preference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "lugares": self.lugares,
            "carreteras": self.carreteras,
            "is_route": self.is_route,
            "route_from": self.route_from,
            "route_to": self.route_to,
            "source_preference": self.source_preference,
        }


def understand_query(query: str) -> QueryUnderstanding:
    normalized_query = normalize_for_matching(query)
    carreteras = extract_roads(query)
    source_preference = extract_source_preference(normalized_query)
    route_from, route_to = extract_route_places(normalized_query)
    lugares = extract_places(
        query=query,
        normalized_query=normalized_query,
        route_places=[route_from, route_to],
    )
    intent = infer_intent(normalized_query, source_preference=source_preference)

    return QueryUnderstanding(
        raw_query=query,
        intent=intent,
        lugares=lugares,
        carreteras=carreteras,
        is_route=bool(route_from and route_to),
        route_from=route_from,
        route_to=route_to,
        source_preference=source_preference,
    )


def infer_intent(
    normalized_query: str,
    source_preference: str | None = None,
) -> str:
    tokens = set(normalized_query.split())
    if tokens & CAMERA_TERMS or any(term in normalized_query for term in CAMERA_TERMS):
        return INTENT_CAMARAS
    if any(term in normalized_query for term in CONGESTION_TERMS):
        return INTENT_CONGESTION
    if any(term in normalized_query for term in OBRAS_CORTES_TERMS):
        return INTENT_OBRAS_CORTES
    if any(term in normalized_query for term in INCIDENCIA_TERMS):
        return INTENT_INCIDENCIAS
    if source_preference and source_preference != "Trafikoa":
        return INTENT_CORPUS
    if any(term in normalized_query for term in CORPUS_TERMS):
        return INTENT_CORPUS
    return INTENT_GENERAL


def extract_roads(query: str) -> list[str]:
    roads = []
    for match in ROAD_PATTERN.finditer(query):
        road = re.sub(r"\s+", "", match.group(0)).upper()
        if road not in roads:
            roads.append(road)
    return roads


def extract_source_preference(normalized_query: str) -> str | None:
    for alias, source in SOURCE_ALIASES.items():
        if alias in normalized_query:
            return source
    return None


def extract_route_places(normalized_query: str) -> tuple[str | None, str | None]:
    patterns = [
        re.compile(r"\bdesde\s+(?P<from>.+?)\s+(?:hasta|a)\s+(?P<to>.+?)(?:[?.!,;]|$)"),
        re.compile(r"\b(?:a|hacia)\s+(?P<to>.+?)\s+desde\s+(?P<from>.+?)(?:[?.!,;]|$)"),
        re.compile(r"\bentre\s+(?P<from>.+?)\s+y\s+(?P<to>.+?)(?:[?.!,;]|$)"),
    ]
    for pattern in patterns:
        match = pattern.search(normalized_query)
        if not match:
            continue
        route_from = clean_place_phrase(match.group("from"))
        route_to = clean_place_phrase(match.group("to"))
        if route_from and route_to:
            return route_from, route_to
    return None, None


def extract_places(
    query: str,
    normalized_query: str,
    route_places: list[str | None] | None = None,
) -> list[str]:
    places: list[str] = []
    for route_place in route_places or []:
        add_unique(places, route_place)

    roadless_query = ROAD_PATTERN.sub(" ", normalized_query)
    for alias, display_name in KNOWN_PLACE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", roadless_query):
            add_unique(places, display_name)

    for phrase in _preposition_place_phrases(roadless_query):
        add_unique(places, clean_place_phrase(phrase))

    for phrase in _capitalized_place_phrases(query):
        add_unique(places, clean_place_phrase(normalize_for_matching(phrase)))

    compact_tokens = [
        token
        for token in roadless_query.split()
        if token not in PLACE_STOPWORDS and token not in SOURCE_ALIASES
    ]
    if not any(route_places or []) and 1 <= len(compact_tokens) <= 3:
        add_unique(places, clean_place_phrase(" ".join(compact_tokens)))

    return places


def clean_place_phrase(phrase: str | None) -> str | None:
    if not phrase:
        return None
    normalized = normalize_for_matching(phrase)
    normalized = ROAD_PATTERN.sub(" ", normalized)
    normalized = re.sub(r"[?.!,;:()]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None

    tokens = normalized.split()
    while tokens and tokens[0] in {
        "a",
        "al",
        "de",
        "del",
        "desde",
        "el",
        "en",
        "hacia",
        "hasta",
        "la",
        "las",
        "los",
        "ruta",
        "via",
        "vía",
    }:
        tokens.pop(0)

    if "a" in tokens and any(token in {"ruta", "via", "vía", "carretera"} for token in tokens):
        tokens = tokens[tokens.index("a") + 1 :]

    stop_at = None
    for index, token in enumerate(tokens):
        if index > 0 and token in {"desde", "hasta", "hacia", "entre", "para", "con", "sobre"}:
            stop_at = index
            break
    if stop_at is not None:
        tokens = tokens[:stop_at]

    tokens = [
        token
        for token in tokens
        if token not in PLACE_STOPWORDS
        and token not in SOURCE_ALIASES
        and token not in {"carretera", "camino", "direccion", "sentido"}
    ]
    if not tokens:
        return None

    normalized_place = " ".join(tokens)
    if normalized_place in SOURCE_ALIASES:
        return None
    if normalized_place in KNOWN_PLACE_ALIASES:
        return KNOWN_PLACE_ALIASES[normalized_place]
    return " ".join(token.capitalize() for token in tokens)


def normalize_for_matching(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    without_punctuation = re.sub(r"[^\w\s.-]", " ", without_accents)
    without_punctuation = re.sub(r"\s*-\s*", "-", without_punctuation)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def add_unique(values: list[str], value: str | None) -> None:
    if not value:
        return
    normalized_value = normalize_for_matching(value)
    if not normalized_value or normalized_value in SOURCE_ALIASES:
        return
    existing = {normalize_for_matching(item) for item in values}
    if normalized_value not in existing:
        values.append(value)


def _preposition_place_phrases(normalized_query: str) -> list[str]:
    phrases = []
    pattern = re.compile(
        r"\b(?:en|por|desde|hasta|hacia|a|cerca de|junto a)\s+"
        r"(?P<place>[a-z0-9][a-z0-9\s.-]*?)"
        r"(?=\s+(?:desde|hasta|hacia|entre|para|con|sobre|segun|según|y)\b|[?.!,;]|$)"
    )
    for match in pattern.finditer(normalized_query):
        phrases.append(match.group("place"))
    return phrases


def _capitalized_place_phrases(query: str) -> list[str]:
    phrases = []
    pattern = re.compile(
        r"\b[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)*\b"
    )
    for match in pattern.finditer(query):
        value = match.group(0).strip()
        normalized_value = normalize_for_matching(value)
        if normalized_value in PLACE_STOPWORDS or normalized_value in SOURCE_ALIASES:
            continue
        if normalized_value in {"hay", "que", "muestrame"}:
            continue
        phrases.append(value)
    return phrases
