# 💼 Career Portal

A Django-based recruitment and resume-screening platform that connects **HR/Recruiters** with **Job Candidates**. It automates initial screening by parsing resumes and job descriptions (with OCR for scanned resumes) and producing a weighted match score for every applicant.

![Django](https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![Tesseract](https://img.shields.io/badge/Tesseract_OCR-3C873A?style=flat-square)

---

## ✨ Features

### 👤 Candidate
- Register and log in, then browse and search open jobs
- Apply with a resume and optional cover letter
- Save jobs for later, and track applications and their status
- View scheduled interviews (date/time, location or meeting link, notes)
- Maintain a detailed profile: employment history, education, projects and desired job profile
- Profile completion score
- View and download offer letters, and upload onboarding documents
- Account settings: notification preferences, change password, log out other sessions, deactivate account

### 🧑‍💼 HR / Recruiter
- Dashboard with posted jobs and recent applicants
- Create, edit, open and close job postings
- View applicants per job, or across all jobs, with resume-match results
- Update application status (Applied, Processing, Rejected, Hired)
- Schedule interviews and track them (Scheduled, Completed, Cancelled)
- Generate offer letters (role, salary, joining date, reporting manager, message, attachment)
- Searchable **Talent Pool** of all registered candidates, with profile views and resume downloads
- **Quick Screen** tool: upload a job description and multiple resumes, get a ranked list, and export it to CSV

### 🛠️ Admin
- Django Admin for user profiles, jobs and applications

---

## 🧠 Resume Screening Engine

The screening logic is split into separate modules so it stays easy to maintain:

| Module | Purpose |
|---|---|
| Resume Parser | Extracts skills, experience, education, certifications, projects and keywords from resumes |
| JD Parser | Extracts required skills, experience, education, certifications and keywords from job descriptions |
| OCR Module | Reads scanned or image-based resumes using Tesseract |
| Image Processing | OpenCV preprocessing to improve scans before OCR |
| Matcher | Compares resume data with job requirements |
| Scorer | Calculates the weighted match score |
| Ranking | Ranks candidates by score |
| Pipeline | Connects all of the above into one workflow |

**Pipeline:** upload → OCR / document loading → text extraction → resume parsing → job-description parsing → matching → scoring → score and breakdown stored with the application.

**Matching techniques:** skill, experience, education, certification and keyword matching, plus semantic similarity using TF-IDF and cosine similarity (with optional sentence-embedding support).

### Score weighting

| Component | Weight |
|---|---|
| Skills | 40% |
| Experience | 30% |
| Education | 10% |
| Certifications | 10% |
| Projects / keyword relevance | 10% |

Supported resume formats: PDF (PyMuPDF), Word (python-docx) and scanned images (OpenCV + Tesseract OCR).

---

## 🔄 Recruitment Workflow

1. A user registers as an HR/Recruiter or a Candidate
2. HR posts a job, and candidates browse and apply
3. The screening engine parses the resume and calculates a match score
4. HR reviews applicants, profiles and scores, then schedules interviews
5. HR updates the status and, for selected candidates, generates an offer letter
6. The candidate views the offer and uploads onboarding documents

---

## 🧰 Tech Stack

- **Backend:** Python, Django (built-in authentication, role-based access via a `UserProfile` model)
- **Database:** SQLite
- **Document processing:** OpenCV, Tesseract OCR, PyMuPDF, python-docx
- **Matching:** TF-IDF / cosine similarity (optional sentence embeddings)
- **Frontend:** Django templates, HTML, CSS, JavaScript

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and available on your PATH

### Installation

```bash
# Clone the repository
git clone https://github.com/harini84-mannam/<repo-name>.git
cd <repo-name>

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations and create an admin user
python manage.py migrate
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Then open http://127.0.0.1:8000/ in your browser.

---

## 🔐 Security & Access Control

- HR-only and candidate-only views are protected, so users cannot open pages meant for the other role
- Authentication uses Django's built-in system
- Users can end all other active sessions from Account Settings

---

## 📸 Screenshots

<!-- Add screenshots here, for example:
![Candidate Dashboard](screenshots/candidate-dashboard.png)
![Resume Match Result](screenshots/match-result.png)
-->

---

## 👩‍💻 Author

**Harini Mannam**
[Portfolio](https://hariniport-hwshwlfa.manus.space/) · [LinkedIn](https://www.linkedin.com/in/harini-mannam-052aa730b/) · [GitHub](https://github.com/harini84-mannam)

Built during my Software Development Internship at Meslova Systems.
