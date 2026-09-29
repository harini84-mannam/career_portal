# combines all the individual match scores from matcher.py into one
# final weighted score for a resume vs a JD.

from .matcher import (
    skill_match, experience_match, education_match,
    certification_match, keyword_match, semantic_similarity,
)

WEIGHTS = {
    "skills": 0.40,
    "experience": 0.30,
    "education": 0.10,
    "certifications": 0.10,
    "projects_keywords": 0.10,
}


def score_resume(resume: dict, jd: dict) -> dict:
    # resume = output from resume_parser.parse_resume()
    # jd = output from jd_parser.parse_jd()
    


    skills_result = skill_match(resume.get("raw_text", ""), jd["all_skills"])
    skills_score = skills_result["score"]

    exp_score = experience_match(resume["years_experience"], jd["experience_required_years"])

    edu_score = education_match(resume["education"], jd["education_required"])

    cert_score = certification_match(resume["certifications"], jd["certifications_required"])

    # projects & keywords - half keyword hit rate, half semantic
    # similarity between the resume's project section and the JD
    project_text = resume.get("projects_text") or resume.get("raw_text", "")
    kw_score = keyword_match(resume.get("raw_text", ""), jd["keywords"])
    sem_score = semantic_similarity(project_text, jd.get("raw_text", ""))
    projects_keywords_score = 0.5 * kw_score + 0.5 * sem_score

    component_scores = {
        "skills": skills_score,
        "experience": exp_score,
        "education": edu_score,
        "certifications": cert_score,
        "projects_keywords": projects_keywords_score,
    }

    # turns off weights for anything the JD didn't actually specify
    active_weights = dict(WEIGHTS)
    if jd.get("experience_required_years", 0) <= 0:
        active_weights["experience"] = 0.0
    if not jd.get("education_required"):
        active_weights["education"] = 0.0

    total_active = sum(active_weights.values())
    if total_active <= 0:
        # edge case : JD specified literally nothing, just fall back to
        # the normal weights so we don't divide by zero
        active_weights = dict(WEIGHTS)
        total_active = sum(active_weights.values())

    # normalize the remaining weights so they add up to 1 again
    overall = sum(
        (active_weights[k] / total_active) * component_scores[k]
        for k in component_scores
    ) * 100

    # overall_text_similarity is only an informational metric
    # and is not included in the final ranking score
    overall_similarity = semantic_similarity(resume.get("raw_text", ""), jd.get("raw_text", ""))

    return {
        "candidate": resume["name"],
        "source_filename": resume.get("source_filename", ""),
        "email": resume.get("email", ""),
        "phone": resume.get("phone", ""),
        "overall_score": round(overall, 2),
        "skills_score": round(skills_score * 100, 2),
        "experience_score": round(exp_score * 100, 2),
        "education_score": round(edu_score * 100, 2),
        "certifications_score": round(cert_score * 100, 2),
        "projects_keywords_score": round(projects_keywords_score * 100, 2),
        "overall_text_similarity": round(overall_similarity * 100, 2),
        "matched_skills": skills_result["matched"],
        "missing_skills": skills_result["missing"],
        "years_experience": resume.get("years_experience", 0.0),
        "education": resume.get("education", []),
        "certifications": resume.get("certifications", []),
    }
