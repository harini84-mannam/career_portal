# common helper functions used everywhere else in the project
# skill list, degree list, regex patterns for email/phone/experience etc

import re

# works even if the exact degree short form isn't listed in DEGREES above
SKILL_ALIASES = {
    "python": ["python", "python3"],
    "java": ["java"],
    "c++": ["c++", "cpp"],
    "c": [r"\bc\b"],
    "javascript": ["javascript", "js", "es6"],
    "typescript": ["typescript"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "nosql": ["nosql", "mongodb", "mongo", "cassandra"],
    "react": ["react", "react.js", "reactjs"],
    "angular": ["angular", "angular.js"],
    "django": ["django"],
    "flask": ["flask"],
    "node.js": ["node.js", "node", "nodejs", "express.js", "express"],
    "html/css": ["html", "css", "html5", "css3"],
    "opencv": ["opencv", "cv2"],
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "keras": ["keras"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"],
    "nlp": ["nlp", "natural language processing"],
    "computer vision": ["computer vision", "cv"],
    "data analysis": ["data analysis", "data analytics"],
    "aws": ["aws", "amazon web services", "ec2", "s3 bucket", "lambda"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud"],
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab", "version control"],
    "linux": ["linux", "unix", "bash", "shell scripting"],
    "rest api": ["rest api", "restful api", "rest", "api development"],
    "spring boot": ["spring boot", "spring"],
    "hadoop": ["hadoop"],
    "spark": ["spark", "pyspark", "apache spark"],
    "tableau": ["tableau"],
    "power bi": ["power bi", "powerbi"],
    "excel": ["excel", "ms excel"],
    "r": [r"\br\b programming", r"\br\b language"],
    "tesseract": ["tesseract", "ocr"],
    "streamlit": ["streamlit"],
    "bootstrap": ["bootstrap"],
    "agile": ["agile", "scrum"],
    "ci/cd": ["ci/cd", "continuous integration", "continuous deployment", "jenkins"],
    "data structures": ["data structures", "dsa", "algorithms"],
}

# all the degree short forms i could think of, grouped by branch
DEGREES = [
    # basic ones - bachelor/master/phd etc, covers most JDs by itself
    "b.tech", "btech", "b.e", "bachelor", "bsc", "b.sc",
    "m.tech", "mtech", "m.e", "master", "msc", "m.sc",
    "mba", "phd", "ph.d", "doctorate", "doctoral", "diploma",
    "associate degree", "associate's degree",
    # commerce
    "b.com", "bcom", "m.com", "mcom", "bba", "mca", "bca",
    # arts / social work
    "b.a", "ba", "m.a", "ma", "bsw", "msw",
    # law
    "llb", "ll.b", "llm", "ll.m", "jd",
    # medical / nursing
    "mbbs", "md", "bds", "mds", "bsn", "msn", "rn", "b.pharm", "m.pharm",
    "pharmd", "dnp", "np",
    # education
    "b.ed", "bed", "m.ed", "med",
    # architecture
    "b.arch", "m.arch",
    # school level
    "high school diploma", "vocational training", "certificate program",
]

# for these we only match if they're written in CAPS like "BE" not "be"
AMBIGUOUS_SHORT_DEGREES = ["BE", "ME", "BA", "MA", "MD"]


#  it works even if the exact degree short form isn't in the DEGREES list above
DEGREE_LEVEL_WORDS = ["bachelor", "master", "doctorate", "doctoral", "associate", "diploma"]
DEGREE_FIELD_RE = re.compile(
    r"\b(" + "|".join(DEGREE_LEVEL_WORDS) + r")'?s?\s*(?:degree)?\s*(?:of|in)\s+"
    r"([A-Za-z][A-Za-z &/-]{2,40}?)(?:[.,;\n]|$| or )",
    re.IGNORECASE,
)

CERT_KEYWORDS = [
    "certified", "certification", "certificate", "aws certified",
    "pmp", "cisco", "ccna", "comptia", "azure certified",
    "google certified", "scrum master", "six sigma",
]

# regex patterns used to extract email, phone number, and years of experience
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4})"
)
YEARS_EXP_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)?",
    re.IGNORECASE,
)

# NEW: date-range experience parsing. A lot of resumes (including ones
# using this platform) list roles as date ranges - "11 May 2026 - 9 Oct
# 2026", "May 2020 - Present" - and never actually spell out "X years of
# experience" anywhere. The old extract_years_of_experience() only looked
# for that literal phrase, so a resume like that always scored 0.0 years,
# even with real work history on it. This adds a second pass that finds
# "<date> - <date>" ranges and sums up the durations.
MONTH_NAMES = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    "jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
MONTH_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# one side of a range: "11 May 2026", "May 2026", or a bare "2026"
_DATE_SIDE = (
    rf"(?:\d{{1,2}}\s+)?(?:{MONTH_NAMES})\.?\s+\d{{4}}"  # "11 May 2026" / "May 2026"
    rf"|\d{{4}}"  # bare year "2026"
    rf"|present|current|ongoing|now|till\s*date|to\s*date"
)
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE_SIDE})\s*(?:-|–|—|to)\s*(?P<end>{_DATE_SIDE})",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(rf"(?:\d{{1,2}}\s+)?(?P<month>{MONTH_NAMES})\.?\s+(?P<year>\d{{4}})", re.IGNORECASE)
_BARE_YEAR_RE = re.compile(r"^\d{4}$")
_PRESENT_RE = re.compile(r"present|current|ongoing|now|till\s*date|to\s*date", re.IGNORECASE)


def _month_index(text: str, default_month: int) -> int:
    # turns a matched date side into an absolute month index (year*12 + month)
    # for easy subtraction. bare years assume January/December depending
    # on whether they're the start or end of the range.
    from datetime import date
    text = text.strip()
    if _PRESENT_RE.fullmatch(text) or _PRESENT_RE.search(text):
        today = date.today()
        return today.year * 12 + today.month
    m = _MONTH_YEAR_RE.search(text)
    if m:
        month = MONTH_TO_NUM[m.group("month").lower()[:3] if m.group("month").lower()[:3] != "sep" else "sep"]
        # handle "sept" -> "sep" already covered by [:3] slicing to "sep"
        return int(m.group("year")) * 12 + month
    if _BARE_YEAR_RE.match(text):
        return int(text) * 12 + default_month
    return 0


def extract_experience_years_from_dates(text: str) -> float:
    # scans for "<date> - <date>" ranges (role start/end dates), converts
    # each to a duration in months, and sums them up - this is what
    # catches experience on resumes that only ever show dates and never
    # spell out "X years" anywhere.
    total_months = 0
    for m in DATE_RANGE_RE.finditer(text or ""):
        start_months = _month_index(m.group("start"), default_month=1)
        end_months = _month_index(m.group("end"), default_month=12)
        if start_months and end_months and end_months >= start_months:
            duration = end_months - start_months
            total_months += max(duration, 1)  # at least a fractional month for same-month roles
    return round(total_months / 12, 2)


def clean_text(text: str) -> str:
# basic cleanup - remove weird OCR page-break characters,
# collapse extra spaces, and remove unnecessary blank lines
# so parsing later is easier
    if not text:
        return ""
    text = text.replace("\x0c", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_email(text: str) -> str:
# return the first email-like string found in the text
    m = EMAIL_RE.search(text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
# check every possible phone number match and return the first one
# that has a reasonable number of digits (8 to 13) so random
# numbers don't get picked up as phone numbers
    for m in PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 8 <= len(digits) <= 13:
            return m.group(0).strip()
    return ""


def extract_years_of_experience(text: str) -> float:
# find every "X years" mention AND every date range ("May 2020 - Present"
# style role dates), and return whichever signal gives the larger total.
# resumes/JDs often state things multiple ways, so the biggest reliable
# number is usually the right one - and for resumes that only use dates
# (no literal "X years" phrase anywhere), the date-range pass is what
# stops this from just returning 0.0.
    matches = YEARS_EXP_RE.findall(text)
    stated_years = [float(m) for m in matches if m]
    stated_max = max(stated_years) if stated_years else 0.0
    date_derived = extract_experience_years_from_dates(text)
    return max(stated_max, date_derived)




def extract_skills(text: str) -> list:
# check every skill and its aliases to see if any variation appears in the text (case-insensitive)
    text_lower = text.lower()
    found = []
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if alias.startswith(r"\b"):
                pattern = alias
            else:
                pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                found.append(canonical)
                break  # found this skill, no need to check other aliases for it
    return sorted(set(found))


def extract_education(text: str) -> list:
# search for degrees using:
# 1. the normal degree list (case-insensitive)
# 2. ambiguous abbreviations like BE/ME only when written in uppercase
# 3. generic patterns such as "Bachelor of Science in Computer Science"
    text_lower = text.lower()
    found = []
    for deg in DEGREES:
        if re.search(r"\b" + re.escape(deg) + r"\b", text_lower):
            found.append(deg)
    for deg in AMBIGUOUS_SHORT_DEGREES:
        # NOT using text_lower here on purpose - need exact case match
        # otherwise "be" inside a normal sentence gets picked up wrongly
        if re.search(r"\b" + re.escape(deg) + r"\b", text):
            found.append(deg.lower())
    for level, field in DEGREE_FIELD_RE.findall(text):
        phrase = f"{level.lower()} in {field.strip().lower()}"
        found.append(phrase)
    return sorted(set(found))


def extract_education_fields(text: str) -> list:
    # returns only the feild of study 
    return sorted(set(field.strip().lower() for _, field in DEGREE_FIELD_RE.findall(text)))


def extract_certifications(text: str) -> list:
    # scans each line for certification related keywords
    # if it finds, keeps the entire line as a certification entry
    lines = text.split("\n")
    certs = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in CERT_KEYWORDS):
            clean = line.strip(" -•\t")
            if clean and len(clean) < 150:
                certs.append(clean)
    return certs[:15]  # cap it so we don't get a huge list


def extract_name(text: str) -> str:
# it checks the candidate's name by checking the first few lines 
# if there's any email/phone number or something it just skips it 
# if nothing matches , returns " unknown Candidate "
    for line in text.split("\n")[:8]:
        line = line.strip()
        if not line:
            continue
        if EMAIL_RE.search(line) or PHONE_RE.search(line):
            continue
        if any(c.isdigit() for c in line):
            continue
        if "http" in line.lower() or "www." in line.lower():
            continue
        words = line.split()
        if 1 <= len(words) <= 5 and all(w[0:1].isupper() or not w.isalpha() for w in words):
            return line.title() if line.isupper() else line
    return "Unknown Candidate"


# common filler words ignored while checking section headings
_FILLER_WORDS = {"and", "the", "a", "an", "of", "to", "&"}


def _header_vocab(headers: list) -> set:
# split header phrases into individual words
# used to recognize heading lines later
    vocab = set()
    for h in headers:
        vocab.update(re.findall(r"[a-z]+", h.lower()))
    return vocab


def _heading_line_matches(line: str, vocab: set) -> bool:
# check whether a short line looks like a section heading
# even if it doesn't end with a colon
    clean = line.strip(" -•*\t:")
    if not clean:
        return False
    words = re.findall(r"[a-z]+", clean.lower())
    if not words or len(words) > 6:
        return False
    core = [w for w in words if w not in _FILLER_WORDS]
    return bool(core) and all(w in vocab for w in core)


def extract_section(text: str, headers: list, next_headers: list) -> str:
# extracts the text under a section heading until the next heading
# only headings at the beginning of a line are considered and headings without a colon
    def find_positions(hdrs, vocab):

        hits = []
        colon_pat = re.compile(
            "|".join(r"^[ \t]*[-•*]?[ \t]*" + re.escape(h) + r"\s*:(?=.)" for h in hdrs),
            re.IGNORECASE | re.MULTILINE,
        ) if hdrs else None
        if colon_pat:
            for m in colon_pat.finditer(text):
                hits.append((m.start(), m.end()))
        for m in re.finditer(r"(?m)^[ \t]*[-•*]?[ \t]*([^\n]{1,80})$", text):
            if _heading_line_matches(m.group(1), vocab):
                content_start = m.end() + 1 if m.end() < len(text) else m.end()
                hits.append((m.start(), content_start))
        return hits

    start_vocab = _header_vocab(headers)
    start_hits = find_positions(headers, start_vocab)
    if not start_hits:
        return ""
    start_line, start = min(start_hits, key=lambda p: p[0])

    end_vocab = _header_vocab(list(next_headers) + list(headers))
    end_hits = find_positions(list(next_headers) + list(headers), end_vocab)
    end = len(text)
    for line_start, _ in end_hits:
        if line_start > start_line and line_start < end:
            end = line_start
    return text[start:end].strip(" :\n-")


# common section names used while parsing resumes
SECTION_HEADERS = {
    "skills": ["technical skills", "skills", "core competencies"],
    "education": ["education", "academic background", "qualifications"],
    "experience": ["experience", "work experience", "professional experience", "employment history"],
    "projects": ["projects", "academic projects", "personal projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}