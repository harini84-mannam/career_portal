"""
Seeds enough demo jobs, candidates, and applications to actually see
pagination in action (job list, applications list, and candidate
directory all paginate at 20 per page - see Paginator(..., 20) calls in
views.py). With only 1-2 records in each, the pagination controls never
even render.

Every seeded application's resume is a real (if short) synthetic resume
- built from the candidate's own skill list, with a randomised amount of
overlap against the specific job's requirements - and is run through the
ACTUAL scoring pipeline (parse_jd -> parse_resume -> score_resume) at
seed time. That means the score you see on the dashboard is the same
score you'll get if you click "Rescreen resume" on a demo candidate,
instead of a fake random number that collapses the moment it's
re-screened for real.

Demo jobs are tagged with a hidden `is_demo=True` flag rather than a
visible "[DEMO]" marker in the title, so candidates/managers browsing
the app don't see anything that looks unfinished - `--wipe` uses that
flag to find and remove exactly what this command created.

Safe to run more than once - uses get_or_create on usernames, so
re-running just tops up numbers instead of duplicating everything.

Usage (from the project root, same folder as manage.py):
    python manage.py seed_demo_data
    python manage.py seed_demo_data --jobs 30 --candidates 30
    python manage.py seed_demo_data --wipe   # deletes demo data first, then reseeds
"""
import random
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction

from screening.models import UserProfile, Job, Application
from screening.jd_parser import parse_jd
from screening.resume_parser import parse_resume
from screening.scorer import score_resume

DEMO_USERNAME_PREFIX = "demo_candidate_"

JOB_TITLES = [
    "Software Engineer", "Software Developer", "Backend Developer",
    "Frontend Developer", "Full Stack Developer", "Python Developer",
    "Django Developer", "QA Engineer", "DevOps Engineer",
    "Data Analyst", "Machine Learning Engineer", "Mobile App Developer",
    "Cloud Engineer", "Systems Administrator", "Product Analyst",
    "UI/UX Designer", "Technical Support Engineer", "Database Administrator",
    "Site Reliability Engineer", "Application Developer",
]
LOCATIONS = ["Hyderabad", "Bangalore", "Pune", "Chennai", "Remote", "Mumbai"]
SALARY_RANGES = ["₹3L", "₹4L", "₹5L", "₹6L", "₹8L", "₹10L"]

DESCRIPTION_TEMPLATE = (
    "We are looking for a {title} to join our growing engineering team at "
    "Meslova Systems. You will design, build, and maintain software "
    "solutions, collaborate with cross-functional teams, and contribute to "
    "product quality through clean, well-tested code."
)
REQUIREMENTS_TEMPLATE = (
    "0-{max_years} years of experience in software development. "
    "Proficiency in {lang}. Experience with {framework}. "
    "Working knowledge of Git and version control. "
    "Familiarity with SQL and relational databases. "
    "Strong problem-solving and communication skills."
)
LANGUAGES = ["Python", "Java", "JavaScript", "C#", "TypeScript"]
FRAMEWORKS = ["Django", "React", "Spring Boot", "Node.js", "Flask"]

CANDIDATE_SKILLS_POOL = [
    "Python", "Java", "C", "HTML", "CSS", "JavaScript", "React",
    "Django", "Flask", "MySQL", "SQLite", "MongoDB", "Git", "GitHub",
    "Docker", "AWS", "REST APIs", "Pandas", "NumPy", "TypeScript",
]
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Ishaan", "Ananya", "Diya", "Sai",
    "Reyansh", "Kabir", "Meera", "Arjun", "Priya", "Rohan", "Sneha",
    "Karthik", "Divya", "Nikhil", "Pooja", "Varun", "Neha", "Rahul",
    "Kavya", "Manoj", "Shreya", "Suresh", "Anjali", "Vikram", "Riya",
    "Deepak", "Swati",
]
LAST_NAMES = [
    "Sharma", "Reddy", "Kumar", "Rao", "Gupta", "Nair", "Iyer", "Patel",
    "Singh", "Verma", "Naidu", "Pillai", "Mehta", "Chowdary", "Bose",
]
DEGREES = ["B.Tech in Computer Science", "B.Tech in Information Technology", "BCA", "M.Tech in Computer Science"]
STATUS_WEIGHTS = [("applied", 5), ("processing", 3), ("hired", 1), ("rejected", 3)]


def _build_resume_text(first, last, username, skills, experience_years, degree):
    # a short but genuinely parseable resume - real section headers, real
    # skill words - so extract_skills()/extract_education()/etc in
    # resume_parser.py pick up real content instead of matching nothing
    skills_line = ", ".join(skills)
    return (
        f"{first} {last}\n"
        f"{username}@example.com\n\n"
        f"SKILLS\n{skills_line}\n\n"
        f"EXPERIENCE\n"
        f"{experience_years} years of experience in software development, "
        f"working with {skills[0]} and {skills[1] if len(skills) > 1 else skills[0]} "
        f"on backend and frontend features, fixing bugs, and writing tests.\n\n"
        f"EDUCATION\n{degree}\n\n"
        f"PROJECTS\n"
        f"Built and maintained applications using {skills_line}, including REST API "
        f"integration, database design, and version control with Git.\n"
    )


class Command(BaseCommand):
    help = "Seeds demo jobs, candidates, and applications (scored through the real pipeline) so pagination is visible for a walkthrough/demo."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", type=int, default=25, help="Number of demo jobs to create (default 25).")
        parser.add_argument("--candidates", type=int, default=25, help="Number of demo candidates to create (default 25).")
        parser.add_argument("--wipe", action="store_true", help="Delete previously seeded demo data before creating new data.")

    def handle(self, *args, **options):
        num_jobs = options["jobs"]
        num_candidates = options["candidates"]

        if options["wipe"]:
            self._wipe()

        hr_profile = UserProfile.objects.filter(role="hr").first()
        if not hr_profile:
            raise CommandError(
                "No HR/recruiter account found. Log in as your HR account at least once "
                "(so its UserProfile gets created) before running this command."
            )

        with transaction.atomic():
            jobs = self._seed_jobs(hr_profile, num_jobs)
            candidates = self._seed_candidates(num_candidates)
            apps_created = self._seed_applications(jobs, candidates)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {len(jobs)} jobs, {len(candidates)} candidates, "
            f"{apps_created} applications now in the database, scored through the real pipeline."
        ))
        self.stdout.write(
            "Demo candidate login: username 'demo_candidate_1' (etc.), password 'DemoPass123!'"
        )

    def _wipe(self):
        demo_jobs = Job.objects.filter(is_demo=True)
        demo_users = User.objects.filter(username__startswith=DEMO_USERNAME_PREFIX)
        app_count = Application.objects.filter(job__in=demo_jobs).count()
        job_count = demo_jobs.count()
        user_count = demo_users.count()
        Application.objects.filter(job__in=demo_jobs).delete()
        demo_jobs.delete()
        demo_users.delete()  # cascades to UserProfile -> Application as candidate too
        self.stdout.write(f"Wiped {job_count} demo jobs, {user_count} demo candidates, {app_count} linked applications.")

    def _seed_jobs(self, hr_profile, count):
        created = []
        for i in range(count):
            base_title = random.choice(JOB_TITLES)
            lang = random.choice(LANGUAGES)
            framework = random.choice(FRAMEWORKS)
            job = Job.objects.create(
                title=base_title,
                company="Meslova Systems",
                description=DESCRIPTION_TEMPLATE.format(title=base_title),
                requirements=REQUIREMENTS_TEMPLATE.format(
                    max_years=random.choice([2, 3, 4]),
                    lang=lang,
                    framework=framework,
                ),
                location=random.choice(LOCATIONS),
                salary_range=random.choice(SALARY_RANGES),
                posted_by=hr_profile.user,
                status="open",
                is_demo=True,
            )
            # stash these on the instance (not saved to DB) so _seed_applications
            # can build a resume that plausibly overlaps with this specific job
            job._demo_lang = lang
            job._demo_framework = framework
            created.append(job)
        return created

    def _seed_candidates(self, count):
        created = []
        for i in range(1, count + 1):
            username = f"{DEMO_USERNAME_PREFIX}{i}"
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                },
            )
            if was_created:
                user.set_password("DemoPass123!")
                user.save()

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={"role": "candidate"},
            )
            if not profile.skills:
                skills = random.sample(CANDIDATE_SKILLS_POOL, k=random.randint(4, 8))
                profile.skills = ", ".join(skills)
                profile.headline = f"{random.choice(['Junior', 'Mid-level', 'Aspiring'])} {random.choice(JOB_TITLES)}"
                profile.experience_years = round(random.uniform(0, 4), 1)
                if not profile.resume:
                    degree = random.choice(DEGREES)
                    resume_text = _build_resume_text(
                        first, last, username, skills, profile.experience_years, degree
                    )
                    profile.resume.save(
                        f"{username}_resume.txt",
                        ContentFile(resume_text.encode("utf-8")),
                        save=False,
                    )
                profile.save()
            created.append(profile)
        return created

    def _seed_applications(self, jobs, candidates):
        if not jobs or not candidates:
            return 0
        created_count = 0
        statuses, weights = zip(*STATUS_WEIGHTS)
        for profile in candidates:
            job = random.choice(jobs)
            if Application.objects.filter(job=job, candidate=profile).exists():
                continue

            # base skill set comes from the candidate's own profile; roll the
            # dice on also including this specific job's key language/
            # framework, so match quality varies realistically across the
            # demo population (some strong matches, some weak ones) instead
            # of everyone scoring in a tight, suspiciously uniform band
            base_skills = [s.strip() for s in profile.skills.split(",") if s.strip()]
            candidate_skills = list(base_skills)
            job_lang = getattr(job, "_demo_lang", None)
            job_framework = getattr(job, "_demo_framework", None)
            if job_lang and random.random() < 0.55 and job_lang not in candidate_skills:
                candidate_skills.append(job_lang)
            if job_framework and random.random() < 0.4 and job_framework not in candidate_skills:
                candidate_skills.append(job_framework)

            first, last = profile.user.first_name or "Demo", profile.user.last_name or "Candidate"
            degree = random.choice(DEGREES)
            resume_text = _build_resume_text(
                first, last, profile.user.username, candidate_skills,
                profile.experience_years or 0.0, degree,
            )

            # run it through the SAME pipeline score_application() uses in
            # views.py, so the score shown here matches what "Rescreen
            # resume" produces later - no more surprise drop from a fake
            # random score down to a near-zero real one
            jd_text = f"{job.title}\n\n{job.description}\n\nSkills Required:\n{job.requirements}"
            jd = parse_jd(jd_text)
            resume = parse_resume(resume_text, source_filename=f"{profile.user.username}_resume.txt")
            result = score_resume(resume, jd)

            status = random.choices(statuses, weights=weights, k=1)[0]
            application = Application(
                job=job,
                candidate=profile,
                status=status,
                match_score=result.get("overall_score", 0.0),
                match_details=result,
            )
            application.resume.save(
                f"{profile.user.username}_{job.id}_resume.txt",
                ContentFile(resume_text.encode("utf-8")),
                save=False,
            )
            application.save()
            created_count += 1
        return created_count