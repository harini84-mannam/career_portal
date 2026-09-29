# handles ranking scored resumes, creating the shortlist,
# and exporting the final results to CSV
# uses Python's built-in csv module to keep dependencies lightweight

import csv
import os


def rank_candidates(scored_list: list) -> list:
# sorts candidates by overall score  then assign rank numbers starting from 1
    ranked = sorted(scored_list, key=lambda r: r["overall_score"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def shortlist_top_n(ranked_list: list, n: int = 3) -> list:
    # just grabs the top N from the already-sorted list
    return ranked_list[:n]


CSV_FIELDS = [
    "rank", "candidate", "source_filename", "email", "phone",
    "overall_score", "skills_score", "experience_score", "education_score",
    "certifications_score", "projects_keywords_score", "overall_text_similarity",
    "years_experience", "matched_skills", "missing_skills", "education", "certifications",
]


def _flatten_row(row: dict) -> dict:
# csv can't store python lists directly, so join list fields into
# comma separated strings before writing
    flat = dict(row)
    for key in ("matched_skills", "missing_skills", "education", "certifications"):
        val = flat.get(key, [])
        flat[key] = ", ".join(val) if isinstance(val, list) else val
    return {k: flat.get(k, "") for k in CSV_FIELDS}


def export_csv(ranked_list: list, path: str) -> str:
    # writes the ranked list out to a csv file
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in ranked_list:
            writer.writerow(_flatten_row(row))
    return path
