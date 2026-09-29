# takes raw resume text (from ocr.py) and pulls out structured fields -
# name, email, phone, skills, education, certifications, years of exp,
# plus the raw text of the experience/projects sections

from .utils import (
    clean_text, extract_email, extract_phone, extract_skills,
    extract_education, extract_certifications, extract_years_of_experience,
    extract_name, extract_section, SECTION_HEADERS,
)


def parse_resume(text: str, source_filename: str = "") -> dict:
    text = clean_text(text)

    name = extract_name(text)
    if name == "Unknown Candidate" and source_filename:
# if we couldn't find a name in the resume,
# use the filename as a fallback so we still have
# something meaningful to display
        base = source_filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        name = base.replace("_", " ").replace("-", " ").title()

    email = extract_email(text)
    phone = extract_phone(text)
    skills = extract_skills(text)
    education = extract_education(text)
    certifications = extract_certifications(text)
    years_experience = extract_years_of_experience(text)

    # grabs the experience and projects sections separately, useful later
    # for the projects/keywords part of the scoring
    experience_block = extract_section(
        text, SECTION_HEADERS["experience"],
        SECTION_HEADERS["education"] + SECTION_HEADERS["projects"] + SECTION_HEADERS["certifications"],
    )
    projects_block = extract_section(
        text, SECTION_HEADERS["projects"],
        SECTION_HEADERS["certifications"] + SECTION_HEADERS["education"],
    )

    return {
        "source_filename": source_filename,
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "education": education,
        "certifications": certifications,
        "years_experience": years_experience,
        "experience_text": experience_block,
        "projects_text": projects_block,
        "raw_text": text,
    }
