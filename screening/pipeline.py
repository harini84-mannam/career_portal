# ties everything together - load JD, load resumes, run OCR, parse,
# score, rank. this is what app.py calls, and it also works as a
# standalone command line script (see the bottom of this file)

import os
from .document_loader import load_document, list_resume_files
from .ocr import extract_text
from .jd_parser import parse_jd
from .resume_parser import parse_resume
from .scorer import score_resume
from .ranking import rank_candidates, shortlist_top_n, export_csv

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def process_jd(jd_path: str) -> dict:
    # loads a JD file and returns the parsed dict
    doc = load_document(jd_path)
    text = extract_text(doc)
    return parse_jd(text)


def process_resume(resume_path: str) -> dict:
    # loads one resume file and returns the parsed dict
    doc = load_document(resume_path)
    text = extract_text(doc)
    return parse_resume(text, source_filename=os.path.basename(resume_path))


def run_pipeline(jd_path: str, resume_paths: list, top_n: int = 3, save_csv: bool = True) -> dict:
    # runs the whole thing end to end for a JD + list
    # of resume file paths, returns the ranked results 
    jd = process_jd(jd_path)

    scored = []
    for path in resume_paths:
        try:
            resume = process_resume(path)
            scored.append(score_resume(resume, jd))
        except Exception as e:
            # if one resume fails to process it doesn't let it crash the whole batch 
            # it just gives it a zero score and keep going
            scored.append({
                "candidate": os.path.basename(path),
                "source_filename": os.path.basename(path),
                "email": "", "phone": "",
                "overall_score": 0.0, "skills_score": 0.0, "experience_score": 0.0,
                "education_score": 0.0, "certifications_score": 0.0,
                "projects_keywords_score": 0.0, "overall_text_similarity": 0.0,
                "matched_skills": [], "missing_skills": [], "years_experience": 0.0,
                "education": [], "certifications": [],
                "error": str(e),
            })

    ranked = rank_candidates(scored)
    shortlist = shortlist_top_n(ranked, n=top_n)

    result = {"jd": jd, "ranked": ranked, "shortlist": shortlist}

    if save_csv:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        export_csv(ranked, os.path.join(OUTPUT_DIR, "ranked_candidates.csv"))


    return result


def run_pipeline_from_folders(jd_path: str, resumes_folder: str, top_n: int = 3) -> dict:
    # just gives it a folder of resumes instead of a list of individual file paths
    resume_paths = list_resume_files(resumes_folder)
    return run_pipeline(jd_path, resume_paths, top_n=top_n)


def _print_report(out: dict, top_n: int):
    # prints a readable summary to the terminal when running from CLI
    jd = out["jd"]
    print("\n" + "=" * 78)
    print("JOB DESCRIPTION SUMMARY")
    print("=" * 78)
    print(f"Required skills : {', '.join(jd['required_skills']) or '(none detected)'}")
    print(f"Preferred skills: {', '.join(jd['preferred_skills']) or '(none detected)'}")
    print(f"Experience req. : {jd['experience_required_years']}+ years")
    print(f"Education req.  : {', '.join(jd['education_required']) or '(not specified)'}")

    print("\n" + "=" * 78)
    print("RANKED CANDIDATES")
    print("=" * 78)
    header = f"{'Rank':<5}{'Candidate':<22}{'Score':<8}Skills Matched / Missing"
    print(header)
    print("-" * 78)
    for r in out["ranked"]:
        matched = ", ".join(r["matched_skills"]) or "-"
        missing = ", ".join(r["missing_skills"]) or "-"
        print(f"{r['rank']:<5}{r['candidate']:<22}{r['overall_score']:<8}"
              f"matched: {matched}")
        print(f"{'':<35}missing: {missing}")

    print("\n" + "=" * 78)
    print(f"TOP {top_n} SHORTLIST")
    print("=" * 78)
    for r in out["shortlist"]:
        print(f"  #{r['rank']}  {r['candidate']:<22} {r['overall_score']}%  "
              f"({r['email'] or 'no email'}, {r['years_experience']} yrs)")

    print(f"\nFull results  -> output/ranked_candidates.csv")



if __name__ == "__main__":
    # lets you run this straight from the command line 
    import argparse
    parser = argparse.ArgumentParser(
        description="AI Resume Screening System (CLI) -- ranks resumes against a Job Description."
    )
    parser.add_argument("--jd", required=True, help="Path to job description file (.txt or .pdf)")
    parser.add_argument("--resumes", required=True, help="Folder containing resume files (.pdf/.jpg/.png/.txt)")
    parser.add_argument("--top", type=int, default=3, help="Top N candidates to shortlist (default: 3)")
    args = parser.parse_args()

    out = run_pipeline_from_folders(args.jd, args.resumes, top_n=args.top)
    _print_report(out, args.top)
