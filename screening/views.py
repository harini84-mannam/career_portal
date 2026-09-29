import os
import uuid
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, EmailMessage
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.db.models import F, Q, Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    UserProfile, Job, Application, SavedJob, Interview,
    DesiredProfile, EmploymentHistory, EducationDetail, Project,
    OfferLetter, CandidateDocument
)
from .pipeline import run_pipeline

BASE_DIR = os.path.dirname(__file__)
UPLOAD_JD_DIR = os.path.join(BASE_DIR, "uploads", "job_description")
UPLOAD_RESUME_DIR = os.path.join(BASE_DIR, "uploads", "resumes")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

for d in (UPLOAD_JD_DIR, UPLOAD_RESUME_DIR, OUTPUT_DIR):
    os.makedirs(d, exist_ok=True)

ALLOWED_JD_EXT = {"txt", "pdf"}
ALLOWED_RESUME_EXT = {"pdf", "jpg", "jpeg", "png", "txt"}
ALLOWED_OFFER_EXT = {"pdf", "doc", "docx"}

def allowed(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions

# Increments  a profile metric by one.
def increment_profile_metric(profile_id, field_name):
    """Increments a profile metric."""
    if field_name not in {"search_appearances", "recruiter_actions"}:
        raise ValueError("Unsupported profile metric")
    UserProfile.objects.filter(pk=profile_id).update(**{field_name: F(field_name) + 1})

# track a candidate profile view once per hr user each day.
def mark_candidate_profile_seen(request, profile_id):
    """Only counts a profile view once per HR user each day."""

    today = timezone.localdate().isoformat()
    event_key = f"{request.user.pk}:{profile_id}:{today}"
    seen_profiles = request.session.get("candidate_profile_views", [])
    if event_key in seen_profiles:
        return False
    request.session["candidate_profile_views"] = (seen_profiles + [event_key])[-500:]
    request.session.modified = True
    return True

# displays the landing page for the application.
def landing(request):
# We always stay on the landing page (Candidate Evaluation Desk) during this phase.
    return render(request, "screening/landing.html")

# displays the privacy policy page.
def privacy_policy(request):
    return render(request, "screening/privacy_policy.html")

# displays the terms of service page
def terms_of_service(request):
    return render(request, "screening/terms_of_service.html")

# displays the support page.
def support(request):
    return render(request, "screening/support.html")

# handles user registration and creates a new user profile.
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        role = request.POST.get("role", "candidate")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect("register")

        # Check email as well as username to avoid duplicate accounts.
        # Email matching is case-insensitive since it's used for resets
        # and interview notifications.

        if email and User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password)
        profile = UserProfile.objects.create(
            user=user,
            role=role,
            company_name="Meslova Systems" if role == 'hr' else ''
        )
        login(request, user)
        messages.success(request, f"Welcome, {username}! Account created successfully.")
        if role == 'hr':
            return redirect('hr_dashboard')
        return redirect('candidate_dashboard')

    return render(request, "screening/register.html")

# Handles user login and redirects them to the appropriate dashboard.
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            try:
                if user.profile.role == 'hr':
                    return redirect('hr_dashboard')
            except UserProfile.DoesNotExist:
                pass
            return redirect('candidate_dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, "screening/login.html")

# logs the user out and redirects them to the landing page.
def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('landing')

# Displays the candidate dashboard with applications, saved jobs, interviews, and job recommendations.
def candidate_dashboard(request):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    profile = request.user.profile
    
    # Applications
    applications = Application.objects.filter(candidate=profile).select_related('job').order_by('-applied_at')
    active_apps = applications.exclude(status__in=['rejected', 'hired'])
    # show hired applications separately.
    hired_applications = applications.filter(status='hired').select_related('job')
    
    # Saved Jobs
    saved_jobs = SavedJob.objects.filter(candidate=profile).select_related('job')
    
    # Interviews
    interviews = Interview.objects.filter(application__candidate=profile, status='scheduled').order_by('scheduled_at')
    
    # jobs the candidate hasn't applied to yet
    applied_job_ids = applications.values_list('job_id', flat=True)
    recommendations = Job.objects.filter(status='open').exclude(id__in=applied_job_ids).order_by('?')[:3]
    
    return render(request, 'screening/candidate_dashboard.html', {
        'profile': profile,
        'recommendations': recommendations,
        'applications': applications[:5],
        'hired_applications': hired_applications,
        'active_count': active_apps.count(),
        'saved_count': saved_jobs.count(),
        'interview_count': interviews.count(),
    })

# displays open jobs and allow candidates to search and browse them .
def browse_jobs(request):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    # search jobs by title, company, location, or requirements.
    query = request.GET.get('q', '').strip()
    jobs = Job.objects.filter(status='open').order_by('-created_at')
    if query:
        from django.db.models import Q
        jobs = jobs.filter(Q(title__icontains=query) | Q(company__icontains=query) | Q(location__icontains=query) | Q(requirements__icontains=query))
    # keep the job list paginated
    paginator = Paginator(jobs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'screening/browse_jobs.html', {'jobs': page_obj, 'page_obj': page_obj, 'query': query})

# displays the jobs saved by the candidate.
def saved_jobs(request):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    # get the candidates saved jobs, newest first 
    saved = SavedJob.objects.filter(
        candidate=request.user.profile
    ).select_related('job').order_by('-saved_at')
    return render(request, 'screening/saved_jobs.html', {'saved_jobs': saved})

# displays the candidate's upcoming scheduled interviews in sequential order
def upcoming_interviews(request):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    # shows schedules interviews in Sequential order
    interviews = Interview.objects.filter(
        application__candidate=request.user.profile,
        status='scheduled',
    ).select_related('application__job').order_by('scheduled_at')
    return render(request, 'screening/upcoming_interviews.html', {'interviews': interviews})

# adds or removes a job from the candidate's saved jobs.
def toggle_saved_job(request, job_id):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    if request.method != 'POST':
        return redirect('job_detail', job_id=job_id)

    job = get_object_or_404(Job, id=job_id)
    saved, created = SavedJob.objects.get_or_create(
        candidate=request.user.profile,
        job=job,
    )
    if created:
        messages.success(request, f'{job.title} was added to your saved jobs.')
    else:
        saved.delete()
        messages.info(request, f'{job.title} was removed from your saved jobs.')
    return redirect('job_detail', job_id=job.id)

# displays the details of a job and the candidate's applications and saved status.
def job_detail(request, job_id):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    job = get_object_or_404(Job, id=job_id)
    # checks whether the candidate has already applied or saved this job
    already_applied = Application.objects.filter(job=job, candidate=request.user.profile).exists()
    is_saved = SavedJob.objects.filter(job=job, candidate=request.user.profile).exists()
    return render(request, 'screening/job_detail.html', {
        'job': job,
        'already_applied': already_applied,
        'is_saved': is_saved,
    })

# Handles a candidate's job application and screens the submitted application.
def apply_job(request, job_id):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    job = get_object_or_404(Job, id=job_id)
    if job.status != 'open':
        messages.error(request, 'This role is no longer accepting applications.')
        return redirect('job_detail', job_id=job.id)
    profile = request.user.profile
    # Don't allow the same candidates to apply twice
    if Application.objects.filter(job=job, candidate=profile).exists():
        messages.info(request, 'You have already applied to this role.')
        return redirect('job_detail', job_id=job.id)
    
    # The candidate must have a resume in their profile to apply.
    if not profile.resume:
        messages.error(request, 'Please add a resume to your profile before applying.')
        return redirect('profile_settings')

    if request.method == 'POST':
        # Create application using the existing profile resume.
        application = Application(
            job=job, 
            candidate=profile, 
            cover_letter=request.POST.get('cover_letter', '').strip(), 
            status='applied',
            resume=profile.resume.name
        )
        application.save()
        score_application(application)
        messages.success(request, 'Application submitted. Your resume has been screened against the role brief.')
        return redirect('my_applications')
    return redirect('job_detail', job_id=job.id)

# displays the candidate's submitted applications
def my_applications(request): # shows the candidate's applications, newest first.
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    applications = Application.objects.filter(candidate=request.user.profile).select_related('job').prefetch_related('interviews').order_by('-applied_at')
    return render(request, 'screening/my_applications.html', {'applications': applications})

# displays the candidates application details, offer letter, and document upload options.
def candidate_application_detail(request, application_id):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial
    application = get_object_or_404(
        Application.objects.select_related('job').prefetch_related('interviews', 'documents'),
        id=application_id, candidate=request.user.profile,
    )
    # only shows offer letter after hr has sent them.
    offer = OfferLetter.objects.filter(
        application=application,
        is_sent=True,
    ).exclude(letter_file='').first()

    # Mark the offer letter as viewed the first time the candidate opens it.
    if offer and offer.viewed_at is None:
        offer.viewed_at = timezone.now()
        offer.save(update_fields=['viewed_at'])

    if request.method == 'POST' and offer:
        for doc_type, _label in CandidateDocument.DOC_TYPE_CHOICES:
            if doc_type == 'degree':
                for uploaded_file in request.FILES.getlist('doc_degree'):
                    CandidateDocument.objects.create(
                        application=application,
                        doc_type=doc_type,
                        file=uploaded_file,
                    )
            else:
                uploaded_file = request.FILES.get(f'doc_{doc_type}')
                if uploaded_file:
                    CandidateDocument.objects.update_or_create(
                        application=application, doc_type=doc_type,
                        defaults={'file': uploaded_file},
                    )
        messages.success(request, 'Documents uploaded.')
        return redirect('candidate_application_detail', application_id=application.id)

    document_status = []
    for doc_type, label in CandidateDocument.DOC_TYPE_CHOICES:
        document_status.append({
            'type': doc_type,
            'label': label,
            'documents': list(application.documents.filter(doc_type=doc_type).order_by('-uploaded_at')),
            'multiple': doc_type == 'degree',
        })

    return render(request, 'screening/candidate_application_detail.html', {
        'application': application,
        'offer': offer,
        'document_status': document_status,
    })

# Downloads the offer letter for the candidate's application.
def download_candidate_offer(request, application_id):
    denial = _require_role(request, 'candidate')
    if denial:
        return denial

    application = get_object_or_404(
        Application.objects.select_related('candidate__user'),
        id=application_id,
        candidate=request.user.profile,
    )
    offer = get_object_or_404(OfferLetter, application=application, is_sent=True)
    # the offer may wxist before the file is ready
    if not offer.letter_file:
        messages.error(request, 'The offer letter file is not available yet.')
        return redirect('candidate_application_detail', application_id=application.id)

    filename = os.path.basename(offer.letter_file.name)
    return FileResponse(
        offer.letter_file.open('rb'),
        as_attachment=True,
        filename=filename,
    )

# allows the user to view and update their profile settings.
def profile_settings(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile = request.user.profile
    
    desired_profile = None
    if profile.role == 'candidate':
        desired_profile, _ = DesiredProfile.objects.get_or_create(profile=profile)

    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save(update_fields=['first_name', 'last_name', 'email'])
        
        if profile.role == 'hr':
            profile.company_name = request.POST.get('company_name', '').strip()
            profile.department = request.POST.get('department', '').strip()
        else:
            profile.headline = request.POST.get('headline', '').strip()
            profile.bio = request.POST.get('bio', '').strip()
            profile.skills = request.POST.get('skills', '').strip()
            try:
                profile.experience_years = float(request.POST.get('experience_years', 0) or 0)
            except ValueError:
                profile.experience_years = 0
            if request.FILES.get('resume'):
                profile.resume = request.FILES['resume']
            
            # save the candidates job preferences too.
            if desired_profile:
                desired_profile.industry = request.POST.get('industry', '').strip()
                desired_profile.functional_role = request.POST.get('functional_role', '').strip()
                desired_profile.job_type = request.POST.get('job_type', '').strip()
                desired_profile.preferred_locations = request.POST.get('preferred_locations', '').strip()
                desired_profile.expected_salary = request.POST.get('expected_salary', '').strip()
                desired_profile.save()
            
        profile.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('profile_view')
    
    return render(request, 'screening/profile_settings.html', {
        'profile': profile,
        'desired_profile': desired_profile
    })


@login_required
# displays the user's account settings and preferences.
def account_settings_view(request):
    # Account level settings and preferences.
    return render(request, 'screening/account_settings.html', {'profile': request.user.profile})


@login_required
# updates the users email notification preference.
def update_notification_preference_view(request):
    if request.method == 'POST':
        profile = request.user.profile
        profile.email_notifications_enabled = bool(request.POST.get('email_notifications_enabled'))
        profile.save(update_fields=['email_notifications_enabled'])
        messages.success(request, 'Notification preferences updated.')
    return redirect('account_settings')


@login_required
# logs the user out of all other active sessions.
def logout_other_sessions_view(request):
    # Sessions records dont have a user id, so check the sesssion data.
    if request.method == 'POST':
        from django.contrib.sessions.models import Session
        current_key = request.session.session_key
        other_sessions = Session.objects.filter(expire_date__gte=timezone.now()).exclude(session_key=current_key)
        removed = 0
        for session in other_sessions:
            data = session.get_decoded()
            if str(data.get('_auth_user_id')) == str(request.user.pk):
                session.delete()
                removed += 1
        if removed:
            messages.success(request, f"Logged out of {removed} other device{'s' if removed != 1 else ''}.")
        else:
            messages.info(request, "No other active sessions found for this account.")
    return redirect('account_settings')


@login_required
# deactivates the user's account while keeping their related data.
def deactivate_account_view(request):
    # deactivate the account instead of deleting it to keep related data.
    if request.method == 'POST':
        confirm_text = request.POST.get('confirm_username', '').strip()
        if confirm_text != request.user.username:
            messages.error(request, 'Type your username exactly to confirm deactivation.')
            return redirect('account_settings')
        user = request.user
        user.is_active = False
        user.save(update_fields=['is_active'])
        logout(request)
        messages.info(request, 'Your account has been deactivated. Contact an administrator to reactivate it.')
        return redirect('landing')
    return redirect('account_settings')


@login_required
# allows the user to change their account password.
def change_password_view(request):
    # keep password changes separate from profile updates.
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # keeps the user logged in after changing the password.
            messages.success(request, 'Your password has been changed.')
        else:
            for error_list in form.errors.values():
                for error in error_list:
                    messages.error(request, error)
        return redirect('account_settings')

    return redirect('account_settings')

# displays the user's profile information and job preferences.
def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile = request.user.profile
    
    desired_profile = None
    skills_list = []
    if profile.role == 'candidate':
        desired_profile, _ = DesiredProfile.objects.get_or_create(profile=profile)
        if profile.skills:
            # Split by comma and strip each skill
            skills_list = [s.strip() for s in profile.skills.split(',') if s.strip()]
    
    return render(request, 'screening/profile_view.html', {
        'profile': profile,
        'desired_profile': desired_profile,
        'skills_list': skills_list
    })

# adds employement history to the candidate's profile
def add_employment(request):
    if not request.user.is_authenticated or request.user.profile.role != 'candidate':
        return redirect('login')
    if request.method == 'POST':
        EmploymentHistory.objects.create(
            profile=request.user.profile,
            company=request.POST.get('company'),
            job_title=request.POST.get('job_title'),
            start_date=request.POST.get('start_date'),
            # current jobs dont have an end date
            end_date=request.POST.get('end_date') or None,
            is_current=request.POST.get('is_current') == 'on',
            monthly_salary=request.POST.get('monthly_salary', ''),
            description=request.POST.get('description', '')
        )
        return redirect('profile_view')
    return render(request, 'screening/add_employment.html')

# adds education details to the candidate's profile
def add_education(request):
    if not request.user.is_authenticated or request.user.profile.role != 'candidate':
        return redirect('login')
    if request.method == 'POST':
        EducationDetail.objects.create(
            profile=request.user.profile,
            qualification=request.POST.get('qualification'),
            institution=request.POST.get('institution'),
            grading_system=request.POST.get('grading_system', ''),
            score=request.POST.get('score', ''),
            passing_year=request.POST.get('passing_year')
        )
        return redirect('profile_view')
    return render(request, 'screening/add_education.html')

# adds project to the candidate's profile
def add_project(request):
    if not request.user.is_authenticated or request.user.profile.role != 'candidate':
        return redirect('login')
    if request.method == 'POST':
        Project.objects.create(
            profile=request.user.profile,
            title=request.POST.get('title'),
            tools_used=request.POST.get('tools_used'),
            description=request.POST.get('description')
        )
        return redirect('profile_view')
    return render(request, 'screening/add_project.html')

# checks whether the user is authenticated and has the required role.
def _require_role(request, role):
    if not request.user.is_authenticated:
        return redirect('login')
    try:
        if request.user.profile.role != role:
            return redirect('candidate_dashboard' if role == 'hr' else 'hr_dashboard')
    except UserProfile.DoesNotExist:
        return redirect('landing')
    return None

# displays the hr dashboard with recent jobs and application and activity.
def hr_dashboard(request):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    jobs = Job.objects.filter(posted_by=request.user).order_by('-created_at')
    applications = Application.objects.filter(job__posted_by=request.user).select_related('candidate__user', 'job').order_by('-applied_at')
    pending_applications = applications.filter(status__in=['applied', 'processing'])
    context = {
        'jobs': jobs[:5],
        'total_jobs': jobs.count(),
        'open_jobs': jobs.filter(status='open').count(),
        'total_applications': applications.count(),
        'pending_review_count': pending_applications.count(),
        'most_recent_pending': pending_applications.first(),

        'recent_applications': applications[:6],
    }
    return render(request, 'screening/hr_dashboard.html', context)

# creates and publishes a new job posting for the HR user
def post_job(request):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        company = request.POST.get('company', '').strip() or getattr(request.user.profile, 'company_name', '') or request.user.username
        description = request.POST.get('description', '').strip()
        requirements = request.POST.get('requirements', '').strip()
        location = request.POST.get('location', '').strip()
        salary_range = request.POST.get('salary_range', '').strip()
        if not title or not description or not requirements:
            messages.error(request, 'Title, description, and requirements are required.')
            return render(request, 'screening/post_job.html', {'form_data': request.POST})
        job = Job.objects.create(title=title, company=company, description=description, requirements=requirements, location=location, salary_range=salary_range, posted_by=request.user)
        messages.success(request, f'{job.title} is now live.')
        return redirect('my_jobs')
    return render(request, 'screening/post_job.html')

# displays and searches the jobs posted by the HR user.
def my_jobs(request):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    query = request.GET.get('q', '').strip()
    jobs = Job.objects.filter(posted_by=request.user).order_by('-created_at')
    # Search by job title or location
    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(location__icontains=query))
    paginator = Paginator(jobs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'screening/my_jobs.html', {'jobs': page_obj, 'page_obj': page_obj, 'query': query})

# displays and filters applications submitted to the HR user's jobs.
def all_applications(request):
    """Show applications for the HR user's jobs"""
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    applications = Application.objects.filter(job__posted_by=request.user).select_related('candidate__user', 'job').order_by('-applied_at')
    status_filter = request.GET.get('status', '').strip()
    # Both applied and processing count as pending here.
    if status_filter == 'pending':
        applications = applications.filter(status__in=['applied', 'processing'])
    elif status_filter in dict(Application.STATUS_CHOICES):
        applications = applications.filter(status=status_filter)
    paginator = Paginator(applications, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'screening/all_applications.html', {
        'applications': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'total_count': applications.count(),
    })

# opens or closes a job posting for the HR user
def toggle_job_status(request, job_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    job = get_object_or_404(Job, id=job_id, posted_by=request.user)
    job.status = 'closed' if job.status == 'open' else 'open'
    job.save(update_fields=['status'])
    messages.success(request, f'{job.title} is now {job.get_status_display().lower()}.')
    return redirect('my_jobs')

# redirects users from the legacy index page to the landing page
def index(request):
    return redirect("landing")

# Screens uploaded resumes against a job description and displays ranked candidates
def screen(request):
    if request.method != "POST":
        return redirect("landing")

    jd_file = request.FILES.get("jd_file")
    resume_files = request.FILES.getlist("resume_files")
    top_n = 50

    if not jd_file or not resume_files:
        messages.error(request, "Please upload both JD and resumes.")
        return redirect("index")

    jd_path = save_upload(jd_file, UPLOAD_JD_DIR)
    resume_paths = [save_upload(f, UPLOAD_RESUME_DIR) for f in resume_files if allowed(f.name, ALLOWED_RESUME_EXT)]

    try:
        result = run_pipeline(jd_path, resume_paths, top_n=top_n, save_csv=True)
    except Exception as e:
        messages.error(request, f"Screening failed: {e}")
        return redirect("index")

    run_id = uuid.uuid4().hex[:10]
    return render(request, "screening/results.html", {
        "run_id": run_id,
        "jd": result["jd"],
        "ranked": result["ranked"],
        "top_n": top_n,
    })

# downloads the generated candidate ranking or shortlist csv file.
def download(request, which):
    filename = {"ranked": "ranked_candidates.csv", "shortlist": "shortlisted_candidates.csv"}.get(which)
    if not filename:
        raise Http404("Not found")
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        raise Http404("Not found")
    return FileResponse(open(path, "rb"), as_attachment=True, filename=filename)

# Scored a candidates application using the resume and job requirements
def score_application(application):
    """Run the existing OCR / parser / scorer pipeline for one application."""
    import tempfile
    if not application.resume or not application.resume.path:
        return None
    # The parser looks for this header when extracting required skills.
    jd_text = (
        f"{application.job.title}\n\n"
        f"{application.job.description}\n\n"
        f"Skills Required:\n{application.job.requirements}"
    )
    jd_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as jd_file:
            jd_file.write(jd_text)
            jd_path = jd_file.name
        result = run_pipeline(jd_path, [application.resume.path], top_n=1, save_csv=False)
        ranked = result.get('ranked') or []
        if not ranked:
            return None
        row = ranked[0]
        application.match_score = float(row.get('overall_score', 0) or 0)
        application.match_details = row
        application.save(update_fields=['match_score', 'match_details', 'updated_at'])
        return row
    except Exception as exc:
        # keeps the error on the application so it can be checked later.
        application.match_details = {'error': str(exc)}
        application.save(update_fields=['match_details', 'updated_at'])
        return None
    finally:
        if jd_path and os.path.exists(jd_path):
            os.remove(jd_path)

# displays the list of candidates who applied for a specific job.
def applicant_list(request, job_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    job = get_object_or_404(Job, id=job_id, posted_by=request.user)
    status_filter = request.GET.get('status', '').strip()
    # put the best matches first.
    applications = Application.objects.filter(job=job).select_related('candidate__user').order_by('-match_score', '-applied_at')
    if status_filter in dict(Application.STATUS_CHOICES):
        applications = applications.filter(status=status_filter)
    paginator = Paginator(applications, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'screening/applicants.html', {'job': job, 'applications': page_obj, 'page_obj': page_obj, 'status_filter': status_filter})

# displays an applications details and allow HR to manage the candidate's application
def application_detail(request, application_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    application = get_object_or_404(
        Application.objects.select_related('candidate__user', 'job').prefetch_related('interviews'),
        id=application_id,
        job__posted_by=request.user,
    )

    # Count one profile view per HR user each day.
    if mark_candidate_profile_seen(request, application.candidate_id):
        increment_profile_metric(application.candidate_id, 'search_appearances')

    if request.method == 'POST' and request.POST.get('offer_action') == 'upload_offer':
        if application.status != 'hired':
            messages.error(request, 'Update the application to Hired before uploading an offer letter.')
            return redirect('application_detail', application_id=application.id)

        letter_file = request.FILES.get('letter_file')
        if not letter_file:
            messages.error(request, 'Choose the offer letter document before uploading.')
            return redirect('application_detail', application_id=application.id)
        # only allow the file types supported by the offer letter upload.
        if not allowed(letter_file.name, ALLOWED_OFFER_EXT):
            messages.error(request, 'Upload the offer letter as a PDF, DOC, or DOCX file.')
            return redirect('application_detail', application_id=application.id)

        existing_offer = OfferLetter.objects.filter(application=application).first()
        offer_defaults = {'letter_file': letter_file}
        # Fill in the offer details when creating the first offer.
        if not existing_offer:
            offer_defaults.update({
                'role_title': application.job.title,
                'salary': application.job.salary_range or '',
                'joining_date': None,
            })

        offer, _created = OfferLetter.objects.update_or_create(
            application=application,
            defaults=offer_defaults,
        )
        # Reset the sent/viewed fields whenever a new offer is uploaded.
        offer.is_sent = True
        offer.sent_at = timezone.now()
        offer.viewed_at = None
        offer.save(update_fields=['is_sent', 'sent_at', 'viewed_at'])
        increment_profile_metric(application.candidate_id, 'recruiter_actions')

        candidate_email = application.candidate.user.email
        if candidate_email and application.candidate.email_notifications_enabled:
            email = EmailMessage(
                subject=f'Your offer from {application.job.company}',
                body=(
                    f"Hi {application.candidate.user.get_full_name() or application.candidate.user.username},\n\n"
                    f"Your offer letter for {application.job.title} at {application.job.company} is now available in your Meslova account.\n\n"
                    "Regards,\nMeslova Systems"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[candidate_email],
            )
            # Attach the uploaded offer letter to the notification email.
            offer.letter_file.open('rb')
            email.attach(os.path.basename(offer.letter_file.name), offer.letter_file.read())
            offer.letter_file.close()
            email.send(fail_silently=True)

        messages.success(request, 'Offer letter uploaded and sent to the candidate.')
        return redirect('application_detail', application_id=application.id)

    if request.GET.get('rescreen') == '1':
        score_application(application)
        increment_profile_metric(application.candidate_id, 'recruiter_actions')
        return redirect('application_detail', application_id=application.id)

    # show an existing hire before HR tries to hire this candidate again.
    existing_hire = None
    if application.status != 'hired':
        existing_hire = Application.objects.filter(
            candidate=application.candidate, status='hired'
        ).exclude(pk=application.pk).select_related('job').first()

    # Don't show the schedule form if an interview is already active.
    has_active_interview = application.interviews.filter(status__in=['scheduled', 'completed']).exists()
    has_completed_interview = application.interviews.filter(status='completed').exists()

    return render(request, 'screening/application_detail.html', {
        'application': application,
        'existing_hire': existing_hire,
        'has_active_interview': has_active_interview,
        'has_completed_interview': has_completed_interview,
    })

# displays the complete read-only profile of a candidate for the hr user.
def recruiter_candidate_profile(request, application_id):
    """Render the complete read-only candidate profile for the owning HR user."""
    # make sures only HR users can access candidate profiles from this view.
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    # fetch the application only if it belongs to a job posted by this hr user
    # this also keeps the candidates and job avaliable without extra database queries.
    application = get_object_or_404(
        Application.objects.select_related('candidate__user', 'job'),
        id=application_id,
        job__posted_by=request.user,
    )
    # load the candidates profile along with the related sections that  are
    # displayed on the profile page: employment, education, and projects.
    candidate_profile = get_object_or_404(
        UserProfile.objects.select_related('user').prefetch_related(
            'employment', 'education', 'projects'
        ),
        pk=application.candidate_id,
        role='candidate',
    )
    desired_profile = DesiredProfile.objects.filter(profile=candidate_profile).first()
    skills_list = [
        skill.strip()
        for skill in (candidate_profile.skills or '').split(',')
        if skill.strip()
    ]

    # Count one profile impression per HR viewer, candidate, and calendar day.
    if mark_candidate_profile_seen(request, candidate_profile.pk):
        increment_profile_metric(candidate_profile.pk, 'search_appearances')

    return render(request, 'screening/recruiter_candidate_profile.html', {
        'application': application,
        'candidate_profile': candidate_profile,
        'desired_profile': desired_profile,
        'skills_list': skills_list,
        'employment': candidate_profile.employment.all().order_by('-start_date'),
        'education': candidate_profile.education.all().order_by('-passing_year'),
        'projects': candidate_profile.projects.all(),
    })

# display all registered candidates in the hr talent pool
def talent_pool(request):
    """Every registered candidate, whether or not they've applied to a job."""
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    candidates = UserProfile.objects.filter(role='candidate').select_related('user').order_by('-created_at')
    query = request.GET.get('q', '').strip()
    if query:
        # show HR how many applications each candidate has submitted.
        candidates = candidates.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) | Q(user__email__icontains=query) |
            Q(headline__icontains=query) | Q(skills__icontains=query)
        )
    candidates = candidates.annotate(application_count=Count('applications', distinct=True))
    paginator = Paginator(candidates, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'screening/talent_pool.html', {
        'candidates': page_obj,
        'page_obj': page_obj,
        'query': query,
        'total_count': candidates.count(),
    })

# displays the read-only profile of a registered candidate
def candidate_directory_profile(request, candidate_id):
    """Read-only profile for any registered candidate, independent of any application."""
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    candidate_profile = get_object_or_404(
        UserProfile.objects.select_related('user').prefetch_related('employment', 'education', 'projects'),
        pk=candidate_id,
        role='candidate',
    )
    desired_profile = DesiredProfile.objects.filter(profile=candidate_profile).first()
    skills_list = [
        skill.strip()
        for skill in (candidate_profile.skills or '').split(',')
        if skill.strip()
    ]
    # only show applications this hr user has access to.
    applications_to_us = Application.objects.filter(
        candidate=candidate_profile, job__posted_by=request.user
    ).select_related('job').order_by('-applied_at')
    # count the profile once per hr user each day to keep view metrics accurate.
    if mark_candidate_profile_seen(request, candidate_profile.pk):
        increment_profile_metric(candidate_profile.pk, 'search_appearances')

    return render(request, 'screening/candidate_directory_profile.html', {
        'candidate_profile': candidate_profile,
        'desired_profile': desired_profile,
        'skills_list': skills_list,
        'employment': candidate_profile.employment.all().order_by('-start_date'),
        'education': candidate_profile.education.all().order_by('-passing_year'),
        'projects': candidate_profile.projects.all(),
        'applications_to_us': applications_to_us,
    })


# allows the hr user to download or view a candidate's profile resume
def download_candidate_resume(request, candidate_id):
    """Serve a candidate's general profile resume (not tied to any specific application)."""
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    candidate_profile = get_object_or_404(UserProfile, pk=candidate_id, role='candidate')
    if not candidate_profile.resume:
        messages.error(request, 'This candidate has not uploaded a profile resume.')
        return redirect('candidate_directory_profile', candidate_id=candidate_profile.pk)
    # Track when an HR user accesses a candidate's resume.
    increment_profile_metric(candidate_profile.pk, 'recruiter_actions')
    # use only the original filename so the response doesn't expose the full storage path.
    filename = os.path.basename(candidate_profile.resume.name)
    return FileResponse(candidate_profile.resume.open('rb'), as_attachment=False, filename=filename)

# updates the status of a candidates job application
def update_application_status(request, application_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    application = get_object_or_404(Application, id=application_id, job__posted_by=request.user)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = dict(Application.STATUS_CHOICES)
        if new_status in valid_statuses:
            old_status = application.status
            if new_status != old_status:
                # Workflow restriction: Hired and Rejected are only allowed
                # after at least one interview has been marked as completed.
                if new_status in ['hired', 'rejected']:
                    has_completed_interview = application.interviews.filter(status='completed').exists()
                    if not has_completed_interview:
                        messages.error(
                            request,
                            f"Cannot mark as {valid_statuses[new_status]} until an interview has been completed."
                        )
                        return redirect('application_detail', application_id=application.id)

                # prevents a candidate from being marked as hired for multiple roles at the same time.
                if new_status == 'hired':
                    existing_hire = Application.objects.filter(
                        candidate=application.candidate, status='hired'
                    ).exclude(pk=application.pk).select_related('job').first()
                    if existing_hire:
                        messages.error(
                            request,
                            f"{application.candidate.user.get_full_name() or application.candidate.user.username} "
                            f"is already hired for {existing_hire.job.title}. To hire them for this role instead, "
                            f"first update their status on that application."
                        )
                        return redirect('application_detail', application_id=application.id)
                application.status = new_status
                application.save(update_fields=['status', 'updated_at'])
                # Track this HR action for the candidate.
                increment_profile_metric(application.candidate_id, 'recruiter_actions')
                messages.success(request, f'Application moved to {valid_statuses[new_status]}.')
            else:
                messages.info(request, f'Application is already in {valid_statuses[new_status]} state.')
    return redirect('application_detail', application_id=application.id)

# updates the status of a schedules interview
def update_interview_status(request, interview_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial

    interview = get_object_or_404(
        Interview.objects.select_related('application__job'),
        id=interview_id,
        application__job__posted_by=request.user,
    )

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        valid_statuses = dict(Interview.STATUS_CHOICES)
        if new_status not in valid_statuses:
            messages.error(request, 'Choose a valid interview status.')
        elif interview.status == new_status:
            messages.info(request, f'Interview is already {valid_statuses[new_status].lower()}.')
        else:
            interview.status = new_status
            interview.save(update_fields=['status'])
            # Track this HR action for the candidate.
            increment_profile_metric(interview.application.candidate_id, 'recruiter_actions')
            messages.success(request, f'Interview marked as {valid_statuses[new_status]}.')

    return redirect('application_detail', application_id=interview.application_id)

# schedules an interview for a candidates job application
def schedule_interview(request, application_id):
    denial = _require_role(request, 'hr')
    if denial:
        return denial

    application = get_object_or_404(
        Application.objects.select_related('candidate__user', 'job'),
        id=application_id,
        job__posted_by=request.user,
    )

    if request.method != 'POST':
        return redirect('application_detail', application_id=application.id)
    if application.status not in {'processing', 'hired'}:
        messages.error(request, 'Move the application to Processing before scheduling an interview.')
        return redirect('application_detail', application_id=application.id)

    scheduled_at = parse_datetime(request.POST.get('scheduled_at', '').strip())
    location = request.POST.get('location', '').strip()
    notes = request.POST.get('notes', '').strip()

    if scheduled_at is None:
        messages.error(request, 'Please choose a valid interview date and time.')
        return redirect('application_detail', application_id=application.id)
    if timezone.is_naive(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
    if scheduled_at <= timezone.now():
        messages.error(request, 'The interview must be scheduled for a future date and time.')
        return redirect('application_detail', application_id=application.id)
    if not location:
        messages.error(request, 'Add a meeting link, phone number, or interview location.')
        return redirect('application_detail', application_id=application.id)

    # Cancel the previous scheduled interview when HR reschedules it.
    Interview.objects.filter(application=application, status='scheduled').update(status='cancelled')
    interview = Interview.objects.create(
        application=application,
        scheduled_at=scheduled_at,
        location=location,
        notes=notes,
        status='scheduled',
    )
    # track this HR action for the candidate.
    increment_profile_metric(application.candidate_id, 'recruiter_actions')

    candidate_email = application.candidate.user.email
    # Only send the notification when the candidate has enabled email updates.
    if candidate_email and application.candidate.email_notifications_enabled:
        send_mail(
            subject=f'Interview scheduled for {application.job.title}',
            message=(
                f"Hello {application.candidate.user.get_full_name() or application.candidate.user.username},\n\n"
                f"Your interview for {application.job.title} at {application.job.company} has been scheduled.\n"
                f"When: {interview.scheduled_at.strftime('%B %d, %Y at %I:%M %p')}\n"
                f"Where: {interview.location}\n\n"
                f"Notes: {interview.notes or 'Please be ready a few minutes early.'}\n\n"
                "Regards,\nMeslova Systems"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[candidate_email],
            fail_silently=True,
        )

    messages.success(request, 'Interview scheduled. The candidate can see the details in My Applications.')
    return redirect('application_detail', application_id=application.id)

# provides the hr user with access to the resume attached to an application
def download_application_resume(request, application_id):
    """Serve a resume to the owning HR user and count the resume interaction."""
    denial = _require_role(request, 'hr')
    if denial:
        return denial
    application = get_object_or_404(
        Application.objects.select_related('job'),
        id=application_id,
        job__posted_by=request.user,
    )
    if not application.resume:
        messages.error(request, 'This application does not have a resume.')
        return redirect('application_detail', application_id=application.id)
    # Track the HR user's resume access as a recuriter action.
    increment_profile_metric(application.candidate_id, 'recruiter_actions')
    filename = os.path.basename(application.resume.name)
    return FileResponse(
        application.resume.open('rb'),
        as_attachment=False,
        filename=filename,
    )

# save_upload file with a unique filename to the specified directory
def save_upload(uploaded_file, dest_dir):
    fname = uploaded_file.name
    # add a unique prefix so files with the same name dont overwrite each other.
    safe_name = f"{uuid.uuid4().hex[:8]}_{fname}"
    path = os.path.join(dest_dir, safe_name)
    with open(path, "wb+") as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)
    return path