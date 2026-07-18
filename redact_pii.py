
from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
P_TAG = f"{{{WORD_NS}}}p"
T_TAG = f"{{{WORD_NS}}}t"
XML_SPACE = f"{{{XML_NS}}}space"

ET.register_namespace("w", WORD_NS)


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_RE = re.compile(
    r"(?i)\b(?:https?://)?(?:www\.)?[A-Z0-9.-]+\s*\.\s*"
    r"(?:com|in|org|net|co)(?:/[^\s;,)\"']*)?"
)
SSN_RE = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}\b"
)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CC_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE_CANDIDATE_RE = re.compile(
    r"(?<![\w])(?:\+\s*91[\s-]*)?"
    r"(?:(?:\(?0?\d{2,5}\)?[\s-]+)?\d{3,5}[\s-]+\d{4,8}|"
    r"(?:\(?0?\d{2,5}\)?[\s-]+)?\d{6,8}|\d{10})"
    r"(?![\w])"
)
DOB_CONTEXT_RE = re.compile(
    r"(?i)\b(?:date\s+of\s+birth|birth\s+date|dob|born\s+on)\b"
    r"\s*[:\-]?\s*"
    r"(?P<date>"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
    r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}"
    r")"
)

COMPANY_RE = re.compile(
    r"\b(?:"
    r"(?:[A-Z][A-Za-z0-9&'()./-]*|[A-Z]{2,}|\d+[A-Z]?|of|and|for|the|in|&)"
    r"\s+){0,11}"
    r"(?:[A-Z][A-Za-z0-9&'()./-]*|[A-Z]{2,}|\d+[A-Z]?)"
    r"\s+(?i:Private\s+Limited|Public\s+Limited|Pvt\.?\s+Ltd\.?|"
    r"Limited|Ltd\.?|LLP|L\.L\.P\.|Bank|Trust)\b"
)

HONORIFIC_NAME_RE = re.compile(
    r"\b(?P<title>Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+"
    r"(?P<name>(?:[A-Z][A-Za-z.'-]+|[A-Z]{2,})"
    r"(?:\s+(?:[A-Z][A-Za-z.'-]+|[A-Z]{2,})){1,3})\b"
)
GENERAL_NAME_RE = re.compile(
    r"\b(?:[A-Z][a-zA-Z.'-]+|[A-Z]{2,})"
    r"(?:\s+(?:[A-Z][a-zA-Z.'-]+|[A-Z]{2,})){1,3}\b"
)
CONCAT_NAME_RE = re.compile(
    r"\b(?P<first>[A-Z][a-z]{2,})(?P<middle>[A-Z][a-z]{2,})"
    r"\s+(?P<last>[A-Z][A-Za-z.'-]+)\*?\b"
)
CONTACT_PERSON_RE = re.compile(r"(?i)\bContact\s+Person[s]?\s*:\s*([^;\n]{2,160})")
PROMOTER_RE = re.compile(r"(?i)\b(?:OUR\s+PROMOTERS|PROMOTERS?)\s*:\s*([^.\n]{10,800})")

ADDRESS_AFTER_LABEL_RE = re.compile(
    r"(?i)\b(?:registered\s+office|corporate\s+office|office|"
    r"manufacturing\s+facility|facility|address|located\s+at|situated\s+at|"
    r"having\s+its\s+registered\s+office\s+at|place\s+of\s+business)"
    r"[^:;.]{0,80}(?:at|:)\s*"
    r"(?P<addr>[^;\n]{10,260}?(?:\bIndia\b|\b\d{3}\s?\d{3}\b))"
)

ADDRESS_KEYWORDS = {
    "apartment",
    "area",
    "avenue",
    "baner",
    "bandra",
    "block",
    "building",
    "centre",
    "chakan",
    "city",
    "complex",
    "embassy",
    "facility",
    "farm",
    "floor",
    "g block",
    "industrial",
    "khed",
    "kurla",
    "marg",
    "mumbai",
    "office",
    "pallod",
    "phase",
    "plot",
    "prabhadevi",
    "pune",
    "road",
    "sector",
    "street",
    "taluka",
    "tower",
    "vikhroli",
    "village",
    "wing",
}
ADDRESS_REGIONS = {
    "india",
    "maharashtra",
    "karnataka",
    "delhi",
    "telangana",
    "gujarat",
    "tamil nadu",
    "rajasthan",
    "haryana",
    "uttar pradesh",
    "west bengal",
}
STATE_COUNTRY_RE = re.compile(
    r"(?i)^\s*(?:maharashtra|karnataka|delhi|telangana|gujarat|"
    r"tamil\s+nadu|rajasthan|haryana|uttar\s+pradesh|west\s+bengal)"
    r"\s*,?\s*india\s*$"
)

FIRST_NAMES = {
    "aarav",
    "abhijit",
    "aditya",
    "akash",
    "amit",
    "ananya",
    "anjali",
    "arjun",
    "ashish",
    "deepak",
    "eric",
    "gaurav",
    "hitesh",
    "isha",
    "kishan",
    "kushal",
    "lalit",
    "lokesh",
    "maithili",
    "meera",
    "nisha",
    "parag",
    "prakash",
    "pravin",
    "priya",
    "pushpa",
    "rajesh",
    "rakhi",
    "rashi",
    "rohan",
    "rohit",
    "sachin",
    "sarthak",
    "sheetal",
    "shanti",
    "siddharth",
    "soumitra",
    "soumavo",
    "tushar",
    "vikram",
}
NAME_STOPWORDS = {
    "act",
    "article",
    "auditors",
    "board",
    "book",
    "built",
    "company",
    "corporate",
    "date",
    "details",
    "directors",
    "draft",
    "equity",
    "face",
    "fresh",
    "government",
    "india",
    "issue",
    "limited",
    "market",
    "offer",
    "price",
    "prospectus",
    "public",
    "registered",
    "registrar",
    "regulations",
    "sebi",
    "section",
    "securities",
    "share",
    "stock",
    "telephone",
    "website",
}
ORG_WORDS = {
    "bank",
    "capital",
    "company",
    "corporation",
    "exchange",
    "industries",
    "international",
    "limited",
    "llp",
    "private",
    "securities",
    "trust",
}
COMPANY_LEADING_STOPWORDS = {"the", "our", "this", "such", "each", "any", "and", "or", "by"}


FAKE_PEOPLE = [
    "John Doe",
    "Peter Parker",
    "Aarav Mehta",
    "Maya Rao",
    "Nisha Kapoor",
    "Rahul Menon",
    "Isha Sharma",
    "Vikram Desai",
    "Ananya Sen",
    "Karan Malhotra",
    "Neha Iyer",
    "Rohan Khanna",
    "Meera Joshi",
    "Dev Patel",
    "Tara Nair",
    "Arjun Bhat",
]
FAKE_COMPANIES = [
    "Northstar Components Private Limited",
    "Bluepeak Securities Limited",
    "Evergreen Industrial Park Private Limited",
    "Summit Advisory LLP",
    "Orion Capital Markets Limited",
    "Cedar Logistics Private Limited",
    "Riverstone Bank",
    "Pioneer Manufacturing Limited",
    "Atlas Family Trust",
    "Silverline Ventures Private Limited",
    "Horizon Exchange Limited",
    "Maple Infrastructure Private Limited",
]
FAKE_ADDRESS_LINES = [
    "42 Maple Avenue, Indiranagar, Bengaluru - 560 038",
    "18 Cedar House, Koramangala, Bengaluru - 560 095",
    "91 Lake View Road, Whitefield, Bengaluru - 560 066",
    "7 Orion Towers, Malleshwaram, Bengaluru - 560 003",
    "305 Green Park, Jayanagar, Bengaluru - 560 011",
    "12 Lotus Enclave, Hebbal, Bengaluru - 560 024",
]
FAKE_REGION = "Karnataka, India"
FAKE_ADDRESSES = [f"{line}, {FAKE_REGION}" for line in FAKE_ADDRESS_LINES]

TYPE_PRIORITY = {
    "EMAIL": 100,
    "SSN": 98,
    "CREDIT_CARD": 97,
    "DOB": 96,
    "IP_ADDRESS": 95,
    "PHONE": 94,
    "URL": 92,
    "ADDRESS": 90,
    "COMPANY": 80,
    "FULL_NAME": 70,
}


@dataclass(frozen=True)
class Entity:
    start: int
    end: int
    label: str
    text: str

    @property
    def priority(self) -> int:
        return TYPE_PRIORITY[self.label]


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def redactable_xml_part(name: str) -> bool:
    if not (name.startswith("word/") and name.endswith(".xml")):
        return False
    base = Path(name).name
    return (
        base == "document.xml"
        or base.startswith("header")
        or base.startswith("footer")
        or base in {"footnotes.xml", "endnotes.xml", "comments.xml"}
    )


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(T_TAG))


def iter_paragraphs_from_xml(xml_bytes: bytes) -> Iterable[ET.Element]:
    root = ET.fromstring(xml_bytes)
    yield from root.iter(P_TAG)


def collect_document_text(docx_path: Path) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(docx_path) as zin:
        for name in zin.namelist():
            if not redactable_xml_part(name):
                continue
            try:
                xml_bytes = zin.read(name)
                paragraphs.extend(paragraph_text(p) for p in iter_paragraphs_from_xml(xml_bytes))
            except ET.ParseError:
                continue
    return "\n".join(p for p in paragraphs if p)


def strip_title_prefix(name: str) -> str:
    return re.sub(r"(?i)^\s*(Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+", "", name).strip()


def tokenize_name(candidate: str) -> list[str]:
    cleaned = strip_title_prefix(candidate)
    cleaned = re.sub(r"[^A-Za-z\s.'-]", " ", cleaned)
    return [part.strip(" .'-").lower() for part in cleaned.split() if part.strip(" .'-")]


def is_probable_person(candidate: str, context_hint: bool = False) -> bool:
    tokens = tokenize_name(candidate)
    if not (2 <= len(tokens) <= 4):
        return False
    if any(token in NAME_STOPWORDS or token in ORG_WORDS for token in tokens):
        return False
    if any(len(token) == 1 for token in tokens):
        return False
    return context_hint or tokens[0] in FIRST_NAMES


def clean_contact_segment(segment: str) -> str:
    segment = re.split(
        r"(?i)\b(?:Telephone|Email|Investor|Company\s+Secretary|Compliance\s+Officer)\b",
        segment,
    )[0]
    segment = segment.split(",")[0]
    return normalize_space(segment.strip(" :;/-"))


def collect_name_candidates(document_text: str) -> set[str]:
    candidates: set[str] = set()

    for email in EMAIL_RE.findall(document_text):
        local = email.split("@", 1)[0]
        parts = [p for p in re.split(r"[._+-]+", local) if p.isalpha()]
        generic = {"cs", "connect", "ipo", "pro", "customercare", "customerservice", "ipocmg"}
        if len(parts) >= 2 and parts[0].lower() not in generic:
            name = " ".join(part.capitalize() for part in parts[:3])
            if is_probable_person(name, context_hint=True):
                candidates.add(name)

    for match in CONTACT_PERSON_RE.finditer(document_text):
        field = match.group(1)
        for segment in re.split(r"/| and |\n", field):
            name = clean_contact_segment(segment)
            if is_probable_person(name, context_hint=True):
                candidates.add(name)

    for match in PROMOTER_RE.finditer(document_text):
        field = match.group(1)
        for segment in re.split(r",|\band\b", field, flags=re.IGNORECASE):
            name = clean_contact_segment(segment)
            if is_probable_person(name, context_hint=True):
                candidates.add(name.title())

    for match in HONORIFIC_NAME_RE.finditer(document_text):
        name = match.group("name")
        if is_probable_person(name, context_hint=True):
            candidates.add(name)

    for match in GENERAL_NAME_RE.finditer(document_text):
        name = match.group(0)
        if is_probable_person(name):
            candidates.add(name)

    return {normalize_space(candidate) for candidate in candidates}


def is_valid_ip(candidate: str) -> bool:
    parts = candidate.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def luhn_valid(digits: str) -> bool:
    checksum = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        checksum += value
    return checksum % 10 == 0


def phone_digits(candidate: str) -> str:
    return re.sub(r"\D", "", candidate)


def is_phone(candidate: str, text: str, start: int) -> bool:
    digits = phone_digits(candidate)
    if not (10 <= len(digits) <= 13):
        return False
    if re.search(r"\+\s*91", candidate):
        return True
    context = text[max(0, start - 45) : start].lower()
    labels = ("telephone", "tel", "phone", "mobile", "contact", "call")
    return any(label in context for label in labels)


def trim_company_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    leading_ws = len(text[start:end]) - len(text[start:end].lstrip(" ,.;:()[]"))
    trailing_ws = len(text[start:end]) - len(text[start:end].rstrip(" ,.;:()[]"))
    start += leading_ws
    end -= trailing_ws
    value = text[start:end]

    while True:
        leading = re.match(r"(?i)^([a-z]+)\s+", value)
        if not leading or leading.group(1).lower() not in COMPANY_LEADING_STOPWORDS:
            break
        start += leading.end()
        value = text[start:end]

    value = value.strip(" ,.;:()[]")
    if not value:
        return None
    compact_value = re.sub(r"[\s.]+", " ", value).strip().lower()
    if compact_value in {"private limited", "public limited", "pvt ltd", "pvt. ltd", "family trust"}:
        return None
    words = tokenize_name(value)
    if len(words) < 2:
        return None
    return start, end


def is_compact_person_name(match: re.Match[str]) -> bool:
    first = match.group("first").lower()
    middle = match.group("middle").lower()
    last = match.group("last").strip(".*'-").lower()
    if last in NAME_STOPWORDS or last in ORG_WORDS:
        return False
    return first in FIRST_NAMES or middle in FIRST_NAMES


def address_score(segment: str) -> int:
    lowered = segment.lower()
    score = 0
    if re.search(r"\b\d{3}\s?\d{3}\b", segment):
        score += 2
    if re.search(r"\d", segment):
        score += 1
    if segment.count(",") >= 2:
        score += 1
    if any(keyword in lowered for keyword in ADDRESS_KEYWORDS):
        score += 2
    if any(region in lowered for region in ADDRESS_REGIONS):
        score += 1
    if re.search(r"(?i)\b(?:plot|flat|no\.?|tower|floor|village|taluka|road|marg|phase)\b", segment):
        score += 2
    return score


def segment_spans(text: str) -> Iterable[tuple[int, int]]:
    start = 0
    for match in re.finditer(r"[;\n]", text):
        yield start, match.start()
        start = match.end()
    yield start, len(text)


def find_addresses(text: str) -> list[Entity]:
    entities: list[Entity] = []

    for match in ADDRESS_AFTER_LABEL_RE.finditer(text):
        start, end = match.span("addr")
        value = text[start:end].strip(" ,.;")
        if address_score(value) >= 4:
            start += len(text[start:end]) - len(text[start:end].lstrip(" ,.;"))
            end -= len(text[start:end]) - len(text[start:end].rstrip(" ,.;"))
            entities.append(Entity(start, end, "ADDRESS", text[start:end]))

    for start, end in segment_spans(text):
        segment = text[start:end]
        stripped = segment.strip(" ,.;")
        if not (12 <= len(stripped) <= 260):
            continue
        if STATE_COUNTRY_RE.match(stripped):
            left_trim = len(segment) - len(segment.lstrip(" ,.;"))
            right_trim = len(segment) - len(segment.rstrip(" ,.;"))
            real_start = start + left_trim
            real_end = end - right_trim
            entities.append(Entity(real_start, real_end, "ADDRESS", text[real_start:real_end]))
            continue
        if re.search(r"(?i)\b(email|telephone|investor grievance|contact person)\b", stripped):
            continue
        if address_score(stripped) >= 5:
            left_trim = len(segment) - len(segment.lstrip(" ,.;"))
            right_trim = len(segment) - len(segment.rstrip(" ,.;"))
            real_start = start + left_trim
            real_end = end - right_trim
            entities.append(Entity(real_start, real_end, "ADDRESS", text[real_start:real_end]))

    return entities


class PiiDetector:
    def __init__(self, document_text: str) -> None:
        self.name_candidates = collect_name_candidates(document_text)
        escaped = sorted((re.escape(name) for name in self.name_candidates), key=len, reverse=True)
        self.name_candidate_re = (
            re.compile(r"(?<![A-Za-z])(?:" + "|".join(escaped) + r")(?![A-Za-z])", re.IGNORECASE)
            if escaped
            else None
        )

    def detect(self, text: str) -> list[Entity]:
        entities: list[Entity] = []

        entities.extend(Entity(m.start(), m.end(), "EMAIL", m.group(0)) for m in EMAIL_RE.finditer(text))
        entities.extend(Entity(m.start(), m.end(), "URL", m.group(0)) for m in URL_RE.finditer(text))
        entities.extend(Entity(m.start(), m.end(), "SSN", m.group(0)) for m in SSN_RE.finditer(text))

        for match in CC_CANDIDATE_RE.finditer(text):
            digits = phone_digits(match.group(0))
            if 13 <= len(digits) <= 19 and luhn_valid(digits):
                entities.append(Entity(match.start(), match.end(), "CREDIT_CARD", match.group(0)))

        for match in DOB_CONTEXT_RE.finditer(text):
            start, end = match.span("date")
            entities.append(Entity(start, end, "DOB", text[start:end]))

        for match in IP_RE.finditer(text):
            if is_valid_ip(match.group(0)):
                entities.append(Entity(match.start(), match.end(), "IP_ADDRESS", match.group(0)))

        for match in PHONE_CANDIDATE_RE.finditer(text):
            if is_phone(match.group(0), text, match.start()):
                entities.append(Entity(match.start(), match.end(), "PHONE", match.group(0)))

        entities.extend(find_addresses(text))

        for match in COMPANY_RE.finditer(text):
            trimmed = trim_company_span(text, match.start(), match.end())
            if trimmed:
                start, end = trimmed
                entities.append(Entity(start, end, "COMPANY", text[start:end]))

        for match in HONORIFIC_NAME_RE.finditer(text):
            entities.append(Entity(match.start(), match.end(), "FULL_NAME", match.group(0)))

        if self.name_candidate_re:
            for match in self.name_candidate_re.finditer(text):
                entities.append(Entity(match.start(), match.end(), "FULL_NAME", match.group(0)))

        for match in CONCAT_NAME_RE.finditer(text):
            if is_compact_person_name(match):
                end = match.end()
                if text[end - 1 : end] == "*":
                    end -= 1
                entities.append(Entity(match.start(), end, "FULL_NAME", text[match.start() : end]))

        for match in GENERAL_NAME_RE.finditer(text):
            value = match.group(0)
            if is_probable_person(value):
                entities.append(Entity(match.start(), match.end(), "FULL_NAME", value))

        return prune_overlaps(entities)


def overlaps(a: Entity, b: Entity) -> bool:
    return a.start < b.end and b.start < a.end


def prune_overlaps(entities: list[Entity]) -> list[Entity]:
    accepted: list[Entity] = []
    for entity in sorted(entities, key=lambda e: (-e.priority, -(e.end - e.start), e.start)):
        if not any(overlaps(entity, existing) for existing in accepted):
            accepted.append(entity)
    return sorted(accepted, key=lambda e: e.start)


class FakeFactory:
    def __init__(self) -> None:
        self.mapping: dict[tuple[str, str], str] = {}
        self.counters: Counter[str] = Counter()

    def replacement(self, label: str, original: str) -> str:
        key = (label, normalize_space(original).casefold())
        if key not in self.mapping:
            self.mapping[key] = self._new_replacement(label, original)
        return self.mapping[key]

    def _next_index(self, label: str) -> int:
        self.counters[label] += 1
        return self.counters[label] - 1

    def _new_replacement(self, label: str, original: str) -> str:
        index = self._next_index(label)
        if label == "FULL_NAME":
            replacement = FAKE_PEOPLE[index % len(FAKE_PEOPLE)]
            title = re.match(r"(?i)^\s*(Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+", original)
            if title:
                replacement = f"{title.group(1)}. {replacement}"
            return match_case(original, replacement)
        if label == "EMAIL":
            first, last = FAKE_PEOPLE[index % len(FAKE_PEOPLE)].lower().split()[:2]
            suffix = "" if index < len(FAKE_PEOPLE) else str(index + 1)
            return f"{first}.{last}{suffix}@example.com"
        if label == "PHONE":
            return f"+91 80 4000 {1000 + index:04d}"
        if label == "URL":
            if original.lower().lstrip().startswith("http"):
                return f"https://www.example{index + 1}.com"
            if original.lower().lstrip().startswith("www"):
                return f"www.example{index + 1}.com"
            return f"example{index + 1}.com"
        if label == "COMPANY":
            return match_case(original, FAKE_COMPANIES[index % len(FAKE_COMPANIES)])
        if label == "ADDRESS":
            if STATE_COUNTRY_RE.match(original):
                return FAKE_REGION
            if not re.search(r"(?i)\bIndia\b", original):
                return FAKE_ADDRESS_LINES[index % len(FAKE_ADDRESS_LINES)]
            return FAKE_ADDRESSES[index % len(FAKE_ADDRESSES)]
        if label == "SSN":
            return f"123-45-{6700 + index:04d}"
        if label == "CREDIT_CARD":
            cards = ["4111 1111 1111 1111", "5555 5555 5555 4444", "4000 0000 0000 0002"]
            return cards[index % len(cards)]
        if label == "DOB":
            return "01 January 1990"
        if label == "IP_ADDRESS":
            return f"192.0.2.{10 + index % 200}"
        return "[REDACTED]"


def match_case(original: str, replacement: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", original)
    if letters and letters.isupper():
        return replacement.upper()
    return replacement


def locate_text_node(nodes: list[ET.Element], position: int) -> tuple[int, int]:
    cursor = 0
    for index, node in enumerate(nodes):
        text = node.text or ""
        next_cursor = cursor + len(text)
        if position <= next_cursor:
            return index, position - cursor
        cursor = next_cursor
    if not nodes:
        raise ValueError("Cannot locate position in empty node list")
    return len(nodes) - 1, len(nodes[-1].text or "")


def set_node_text(node: ET.Element, value: str) -> None:
    node.text = value
    if value.startswith(" ") or value.endswith(" "):
        node.set(XML_SPACE, "preserve")


def apply_entities_to_paragraph(paragraph: ET.Element, entities: list[Entity], factory: FakeFactory) -> int:
    text_nodes = list(paragraph.iter(T_TAG))
    if not text_nodes or not entities:
        return 0

    for entity in sorted(entities, key=lambda e: e.start, reverse=True):
        replacement = factory.replacement(entity.label, entity.text)
        start_node_index, start_offset = locate_text_node(text_nodes, entity.start)
        end_node_index, end_offset = locate_text_node(text_nodes, entity.end)

        if start_node_index == end_node_index:
            node = text_nodes[start_node_index]
            text = node.text or ""
            set_node_text(node, text[:start_offset] + replacement + text[end_offset:])
            continue

        start_node = text_nodes[start_node_index]
        end_node = text_nodes[end_node_index]
        start_text = start_node.text or ""
        end_text = end_node.text or ""
        set_node_text(start_node, start_text[:start_offset] + replacement)
        for node in text_nodes[start_node_index + 1 : end_node_index]:
            set_node_text(node, "")
        set_node_text(end_node, end_text[end_offset:])

    return len(entities)


def process_xml(xml_bytes: bytes, detector: PiiDetector, factory: FakeFactory) -> tuple[bytes, Counter[str]]:
    root = ET.fromstring(xml_bytes)
    counts: Counter[str] = Counter()
    for paragraph in root.iter(P_TAG):
        text = paragraph_text(paragraph)
        entities = detector.detect(text)
        if entities:
            apply_entities_to_paragraph(paragraph, entities, factory)
            counts.update(entity.label for entity in entities)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), counts


def redact_docx(input_path: Path, output_path: Path) -> dict[str, object]:
    document_text = collect_document_text(input_path)
    detector = PiiDetector(document_text)
    factory = FakeFactory()

    total_counts: Counter[str] = Counter()
    processed_parts: list[str] = []

    with zipfile.ZipFile(input_path, "r") as zin, zipfile.ZipFile(output_path, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if redactable_xml_part(item.filename):
                try:
                    data, counts = process_xml(data, detector, factory)
                    total_counts.update(counts)
                    processed_parts.append(item.filename)
                except ET.ParseError:
                    pass
            zout.writestr(item, data)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "processed_xml_parts": processed_parts,
        "replacement_instances": dict(sorted(total_counts.items())),
        "unique_replacements": {
            label: count
            for label, count in sorted(
                Counter(label for label, _ in factory.mapping.keys()).items()
            )
        },
        "total_replacement_instances": int(sum(total_counts.values())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redact PII from a .docx file.")
    parser.add_argument("input", type=Path, help="Input .docx file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .docx file. Defaults to '<input>_redacted.docx'.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Optional path for a non-sensitive JSON summary of replacement counts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    if input_path.suffix.lower() != ".docx":
        raise SystemExit("Input must be a .docx file.")
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_name(f"{input_path.stem}_redacted.docx")
    summary = redact_docx(input_path, output_path)

    if args.summary_json:
        args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
