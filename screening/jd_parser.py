import re
from .utils import (
    clean_text, extract_skills, extract_education, extract_certifications,
    extract_years_of_experience, extract_section,
)

PREFERRED_MARKERS = ["preferred", "nice to have", "good to have", "bonus", "plus"]
REQUIRED_MARKERS = ["required", "must have", "mandatory", "essential"]

RESP_HEADERS = ["responsibilities", "roles and responsibilities", "what you'll do", "duties"]
SKILLS_HEADERS = [
    "required skills", "skills required", "skills", "requirements",
    "qualifications", "what you'll need", "what we're looking for",
    "must have", "key skills",
]
NEXT_HEADERS_GENERIC = [
    "qualifications", "requirements", "skills", "responsibilities",
    "about us", "about the company", "benefits", "education",
    "nice to have", "preferred", "perks",
]

# words at the START of a requirement phrase that don't add any real
# meaning - we strip these off so "experience with Docker" just becomes
# "Docker". this loop is applied more than once because sometimes there's
# more than one filler phrase stacked up, like "Proven track record in X"
LEADIN_TRIM_RE = re.compile(
    r"^(strong|excellent|good|solid|proven|demonstrated|advanced|working|"
    r"hands[- ]on|prior|proficiency (in|with)|experience (in|with)|"
    r"knowledge of|familiarity with|understanding of|ability to|able to|"
    r"skills? (in|with)|exposure to|expertise (in|with)|"
    r"track record (in|of)|background (in|of)|record (in|of)|"
    r"strict attention to detail (to|in)?)\s+",
    re.IGNORECASE,
)

# same idea but for junk words at the END of a phrase
TRAILING_TRIM_RE = re.compile(
    r"\s+(is a plus|is preferred|preferred|a plus|is required|required|is essential|essential)\.?$",
    re.IGNORECASE,
)

# stuff we don't want treated as a skill/requirement at all
DROP_PATTERNS = [
    # BUG FIX: only matched "2+ years" style, not range phrases like
    # "0-2 years" or "2-4 yrs" that both real JD postings use - so
    # "0-2 years of experience in software development" was slipping
    # through as if it were a literal required skill.
    re.compile(r"^\d+\s*(?:-\s*\d+)?\+?\s*(years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"\b(degree|bachelor|master|diploma|b\.?tech|m\.?tech)\b", re.IGNORECASE),
    re.compile(r"^(and|or|the|a|an|with|in|of|to|for)$", re.IGNORECASE),
]
MAX_TERM_WORDS = 7
MAX_DYNAMIC_TERMS = 30

# used to spot a line that's basically just a heading, like "Requirements
# and skills" - so we can skip it and not accidentally pull it in as an
# actual requirement
_HEADING_CORE_WORDS = {
    "requirements", "skills", "qualifications", "responsibilities", "duties",
    "preferred", "nice", "have", "bonus", "benefits", "perks", "overview",
    "brief", "description", "role", "required", "must", "good", "plus",
    "key", "essential", "job",
}
_HEADING_FILLER = {"and", "the", "a", "an", "of", "to", "&", "/"}


def _looks_like_heading(line: str) -> bool:
    # returns True if a line is short and made up of only heading-type
    # words (like "Requirements and skills") so we can skip it
    clean = line.strip(" -•*\t:").lower()
    if not clean:
        return True
    words = re.findall(r"[a-z]+", clean)
    if not words or len(words) > 6:
        return False
    core = [w for w in words if w not in _HEADING_FILLER]
    return bool(core) and all(w in _HEADING_CORE_WORDS for w in core)


def _split_required_vs_preferred(text: str) -> tuple:
    # splits the JD into a "required" part and a "preferred/nice to have"
    # part, based on whichever marker phrase shows up FIRST in the text.
    # (originally i just checked markers in list order which was wrong -
    # had to fix it to use whichever one actually appears earliest)
    lower = text.lower()
    best_idx = None
    for marker in PREFERRED_MARKERS:
        idx = lower.find(marker)
        if idx != -1 and (best_idx is None or idx < best_idx):
            best_idx = idx
    if best_idx is None:
        return text, ""
    return text[:best_idx], text[best_idx:]


def _clean_term(term: str) -> str:
    # strips bullet chars and repeatedly trims leading/trailing filler
    # words until nothing more changes
    term = term.strip(" -•*\t.")
    prev = None
    while prev != term:
        prev = term
        term = LEADIN_TRIM_RE.sub("", term).strip()
        term = TRAILING_TRIM_RE.sub("", term).strip()
    term = re.sub(r"\s+", " ", term)
    return term


def _is_valid_term(term: str) -> bool:
    # basic sanity checks before we accept something as a requirement term
    if not term or len(term) < 2 or len(term) > 60:
        return False
    words = term.split()
    if len(words) > MAX_TERM_WORDS:
        return False
    for pat in DROP_PATTERNS:
        if pat.search(term):
            return False
    return True


NONREQ_TRAILING_HEADERS = RESP_HEADERS + ["about us", "about the company", "benefits", "perks"]


def _cut_before_heading(text: str, headers: list) -> str:
    # cuts off text right before whichever heading shows up first,
    # so stuff like a trailing "Responsibilities:" section doesn't
    # bleed into whatever we're extracting
    positions = []
    for h in headers:
        m = re.search(r"(?im)^[ \t]*[-•*]?[ \t]*" + re.escape(h) + r"\s*:?", text)
        if m:
            positions.append(m.start())
    return text[:min(positions)] if positions else text


def extract_requirement_terms(text: str) -> list:
    # this is the main function that reads the JD's own wording and pulls
    # out requirement phrases, instead of relying only on our fixed skill
    # list. works for any job type since it's using the JD's own text.
    #
    # steps:
    #  1. find the Skills/Requirements section
    #  2. go line by line, split each bullet into smaller pieces on
    #     commas/and/or/slashes etc
    #  3. clean up each piece (strip filler words)
    #  4. keep the ones that look like reasonable short phrases

    block = extract_section(text, SKILLS_HEADERS, NEXT_HEADERS_GENERIC)
    if not block:
        # no clean "Skills:" style header found (happens with short
        # "Nice to have" bits) - just use everything, but first cut off
        # the heading line itself and anything unrelated after it
        block = text
        lines = block.split("\n", 1)
        first_line_clean = lines[0].strip(" -•*\t:").lower() if lines else ""
        if first_line_clean in [h.lower() for h in (PREFERRED_MARKERS + SKILLS_HEADERS)]:
            block = lines[1] if len(lines) > 1 else ""
        block = _cut_before_heading(block, NONREQ_TRAILING_HEADERS)

    terms = []
    for line in block.split("\n"):
        line = line.strip(" -•*\t")
        if not line or _looks_like_heading(line):
            continue
        # "and/or" would get chopped weirdly by the bare "/" split below
        # (ends up as "...and" + "or...") so merge it into just "or" first
        line = re.sub(r"\band\s*/\s*or\b", "or", line, flags=re.IGNORECASE)

        # BUG FIX: JDs written as flowing paragraphs (not bullet lists) put
        # multiple requirements in one "line" separated by sentence-ending
        # periods, e.g. "...object-oriented programming, and software
        # design principles. Experience with SQL and relational
        # databases...". The old code only split on commas/and/or/slashes,
        # never on periods, so everything between the last comma of one
        # sentence and the first comma of the next got glued into one
        # giant garbage term like "software design principles. experience
        # with sql" - which then obviously never matches any resume text.
        # Splitting into sentences FIRST, then applying the existing
        # comma/and/or split within each sentence, fixes this.
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            chunks = re.split(r",| and | or | & |/|;| such as ", sentence, flags=re.IGNORECASE)
            for chunk in chunks:
                term = _clean_term(chunk)
                if _is_valid_term(term):
                    terms.append(term.lower())

    # remove duplicates but keep the order they first appeared in
    seen = []
    for t in terms:
        if t not in seen:
            seen.append(t)
    return seen[:MAX_DYNAMIC_TERMS]


def parse_jd(text: str) -> dict:
    # main function - takes raw JD text, returns a dict with everything
    # structured out
    text = clean_text(text)
    required_block, preferred_block = _split_required_vs_preferred(text)

    # layer 1 - known tech skills from our taxonomy list
    taxonomy_required = extract_skills(required_block)
    taxonomy_preferred = extract_skills(preferred_block) if preferred_block else []
    taxonomy_required = [s for s in taxonomy_required if s not in taxonomy_preferred]

    # layer 2 - whatever the JD itself lists as requirements, works for
    # any job type not just tech
    dynamic_required = extract_requirement_terms(required_block)
    dynamic_preferred = extract_requirement_terms(preferred_block) if preferred_block else []
    dynamic_required = [t for t in dynamic_required if t not in dynamic_preferred]

    # combine both layers without duplicating anything
    def _merge(a, b):
        merged = list(a)
        for t in b:
            if t not in merged:
                merged.append(t)
        return merged

    required_skills = _merge(taxonomy_required, dynamic_required)
    preferred_skills = _merge(taxonomy_preferred, dynamic_preferred)
    required_skills = [s for s in required_skills if s not in preferred_skills]

    all_skills = required_skills + [s for s in preferred_skills if s not in required_skills]

    experience_required = extract_years_of_experience(text)
    education_required = extract_education(text)
    certifications = extract_certifications(text)

    responsibilities_block = extract_section(text, RESP_HEADERS, NEXT_HEADERS_GENERIC)
    responsibilities = [
        line.strip(" -•\t")
        for line in responsibilities_block.split("\n")
        if line.strip(" -•\t")
    ][:20]

    # loose keyword list for the tf-idf similarity check later, just
    # grabs any word-ish tokens that aren't super common english words
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9+.#/-]{2,}\b", text)
    stop_generic = {"the", "and", "for", "with", "you", "our", "will", "are", "this", "that"}
    keywords = sorted(set(
        w.lower() for w in words
        if w.lower() not in stop_generic and len(w) > 2
    ))[:100]

    return {
        "raw_text": text,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "all_skills": all_skills,
        "experience_required_years": experience_required,
        "education_required": education_required,
        "certifications_required": certifications,
        "responsibilities": responsibilities,
        "keywords": keywords,
    }