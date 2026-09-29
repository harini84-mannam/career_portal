# compares resumes against job descriptions
# uses a manual TF-IDF + cosine similarity implementation instead of
# scikit-learn, with optional sentence-transformer embeddings when available
# automatically falls back to TF-IDF if the BERT model is unavailable
import math
import re
from collections import Counter

import numpy as np

from .utils import SKILL_ALIASES

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#/-]{1,}")

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "for", "with", "as", "by",
    "at", "from", "that", "this", "these", "those", "it", "its", "we",
    "you", "your", "our", "will", "shall", "can", "should", "would",
    "have", "has", "had", "not", "no", "do", "does", "did", "so", "than",
    "then", "there", "their", "they", "he", "she", "his", "her", "them",
}


def tokenize(text: str) -> list:
    # splits text into lowercase words, ignoring common stopwords
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _term_freq(tokens: list) -> dict:
# calculate how frequently each word appears in a document
# normalized by the total number of words
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    return {term: count / total for term, count in counts.items()}


def _inverse_doc_freq(token_lists: list) -> dict:
# calculate inverse document frequency
# rarer words get higher weights because they carry more meaning
    n_docs = len(token_lists)
    df = Counter()
    for tokens in token_lists:
        for term in set(tokens):
            df[term] += 1
    return {term: math.log((n_docs + 1) / (count + 1)) + 1 for term, count in df.items()}


def _tfidf_vector(tf: dict, idf: dict, vocab: list) -> np.ndarray:
# convert one document into a numeric TF-IDF vector
# using the shared vocabulary from all compared documents
    return np.array([tf.get(term, 0.0) * idf.get(term, 0.0) for term in vocab])


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
# measures the angle between two vectors ; 1 = identical direction, 0 = unrelated
    norm_a, norm_b = np.linalg.norm(vec_a), np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def tfidf_cosine_similarity(text_a: str, text_b: str) -> float:
    # compares 2 pieces of text using tfidf + cosine similarity
    # builds the vocabulary  from just these 2 documents
    tokens_a, tokens_b = tokenize(text_a), tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    idf = _inverse_doc_freq([tokens_a, tokens_b])
    vocab = sorted(idf.keys())
    vec_a = _tfidf_vector(_term_freq(tokens_a), idf, vocab)
    vec_b = _tfidf_vector(_term_freq(tokens_b), idf, vocab)
    return cosine_similarity(vec_a, vec_b)


_st_model = None
_st_available = None  # None = haven't checked yet


def _get_sentence_model():
# loads the sentence-transformers model
# if installation or model loading fails, marks it unavailable
# so future calls directly use the TF-IDF fallback
    global _st_model, _st_available
    if _st_available is False:
        return None
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
            _st_available = True
        except Exception:
            _st_available = False
            return None
    return _st_model


def semantic_similarity(text_a: str, text_b: str) -> float:
    # uses bert embeddings if available, otherwise just uses tfidf
    model = _get_sentence_model()
    if model is not None:
        try:
            emb = model.encode([text_a, text_b])
            return cosine_similarity(np.array(emb[0]), np.array(emb[1]))
        except Exception:
            pass
    return tfidf_cosine_similarity(text_a, text_b)


def skill_match(resume_text: str, jd_terms: list) -> dict:
# compare JD requirements against the resume text
# checks both extracted skills and dynamic JD terms using literal matching
# returns matched terms, missing terms, and an overall match percentage
    resume_lower = (resume_text or "").lower()
    matched, missing = [], []
    for term in jd_terms:
        # BUG FIX: this used to only check the literal canonical term
        # (e.g. "git", "sql") against the resume, completely ignoring the
        # SKILL_ALIASES list that utils.py already defines for exactly
        # this purpose. A resume that says "GitHub" or "MySQL" would get
        # marked as missing "git" / "sql" because those exact standalone
        # words never appear - even though the candidate clearly has the
        # skill. Now, for any term that's a known canonical skill, we
        # check every one of its aliases against the resume and count it
        # as matched if ANY of them show up.
        aliases = SKILL_ALIASES.get(term, [term])
        found = False
        for alias in aliases:
            pattern = alias if alias.startswith(r"\b") else r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, resume_lower):
                found = True
                break
        if found:
            matched.append(term)
        else:
            missing.append(term)
    score = len(matched) / len(jd_terms) if jd_terms else 1.0
    return {"matched": matched, "missing": missing, "score": score}


def experience_match(resume_years: float, required_years: float) -> float:
    # full score if resume meets/exceeds required years,
    # partial credit otherwise
    if required_years <= 0:
        return 1.0
    if resume_years >= required_years:
        return 1.0
    return max(0.0, resume_years / required_years)


def education_match(resume_education: list, required_education: list) -> float:
    # full score if resume has at least one of the required degree types
    if not required_education:
        return 1.0
    resume_set = set(resume_education)
    return 1.0 if resume_set & set(required_education) else 0.0


def certification_match(resume_certs: list, required_certs: list) -> float:
    # checks how many of the required certs show up in the resume's cert list
    if not required_certs:
        return 1.0 if resume_certs else 0.5  # small bonus just for having some certs
    resume_text = " ".join(resume_certs).lower()
    hits = sum(1 for c in required_certs if any(w in resume_text for w in c.lower().split()[:3]))
    return min(1.0, hits / max(1, len(required_certs)))


def keyword_match(resume_text: str, jd_keywords: list) -> float:
# calculates how much of the JD keyword list appears in the resume text
    # BUG FIX: every other *_match function in this file returns 1.0 (full
    # credit) when the JD didn't specify anything to check against -
    # skill_match, experience_match, education_match, and certification_match
    # all do this. This one returned 0.0 instead, which silently forced
    # projects_keywords_score down by half (since it's 0.5*kw_score +
    # 0.5*sem_score) any time jd["keywords"] came back empty, even though
    # that's not the candidate's fault. Made it consistent with the rest.
    if not jd_keywords:
        return 1.0
    resume_lower = resume_text.lower()
    hits = sum(1 for kw in jd_keywords if kw in resume_lower)
    return hits / len(jd_keywords)