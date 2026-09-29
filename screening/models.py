from django.db import models
from django.contrib.auth.models import User

# stores user profile information, including role-specific detials and account preferences
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('hr', 'HR / Recruiter'),
        ('candidate', 'Job Candidate'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='candidate')
    
    # HR specific fields
    company_name = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    
    # Candidate specific fields
    headline = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    skills = models.TextField(blank=True, null=True, help_text="Comma-separated skills")
    experience_years = models.FloatField(default=0.0)
    resume = models.FileField(upload_to='resumes/', blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    search_appearances = models.IntegerField(default=0)
    recruiter_actions = models.IntegerField(default=0)

    # controls whether the user wants to receive email notifications
    email_notifications_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def get_completion_percentage(self):
        # start with a basic completion score and add points for completed profile details
        score = 40
        if self.role == 'hr':
            if self.company_name: score += 20
            if self.department: score += 20
            if self.profile_picture: score += 20
        # candidates profile are completed based on their career information
        else:
            if self.headline: score += 15
            if self.skills: score += 15
            if self.resume: score += 15
            if self.employment.exists(): score += 15
        return min(score, 100)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

# stores job postings created by hr users
class Job(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(help_text="Key skills and requirements for matcher pipeline")
    location = models.CharField(max_length=255, blank=True, null=True)
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posted_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    # Identifies jobs added by the demo data command so they can be removed later
    is_demo = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} at {self.company}"

# stores a candidate's applications for a job, including resume and screening results
class Application(models.Model):
    STATUS_CHOICES = (
        ('applied', 'Applied'),
        ('processing', 'Processing'),
        ('rejected', 'Rejected'),
        ('hired', 'Hired'),
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    candidate = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='applications')
    resume = models.FileField(upload_to='application_resumes/')
    cover_letter = models.TextField(blank=True, null=True)
    
    match_score = models.FloatField(default=0.0)
    match_details = models.JSONField(blank=True, null=True)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='applied')
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidate.user.username} -> {self.job.title} ({self.status})"

# stores jobs saved by candidates application for later reference
class SavedJob(models.Model):
    candidate = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('candidate', 'job')

    def __str__(self):
        return f"{self.candidate.user.username} saved {self.job.title}"

# stores jobs saved by candidates for later reference
class OfferLetter(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='offer_letter')
    role_title = models.CharField(max_length=255, blank=True)
    salary = models.CharField(max_length=100, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    reporting_manager = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    # stores the offer letter document uploaded by HR
    letter_file = models.FileField(upload_to='offer_letters/', blank=True, null=True)
    # shows whether HR has sent the offer to the candidate
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    # Records when the candidate first viewed the offer letter
    viewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Offer for {self.application.candidate.user.username} - {self.role_title}"

# stores documents uploaded by candidates for their jobs applications
class CandidateDocument(models.Model):
    DOC_TYPE_CHOICES = (
        ('degree', 'Degree / Education Certificate'),
        ('pan', 'PAN Card'),
        ('aadhaar', 'Aadhaar Card'),
        ('photo', 'Passport-size Photo'),
        ('relieving', 'Previous Employment / Relieving Letter'),
    )
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='candidate_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_doc_type_display()} for {self.application.candidate.user.username}"

# stores interview scheduling and status information for a job application
class Interview(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews')
    scheduled_at = models.DateTimeField()
    location = models.CharField(max_length=255, help_text="Meeting link or physical address")
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview for {self.application.candidate.user.username} - {self.application.job.title}"

# stores a candidates employement history and work experience
class EmploymentHistory(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='employment')
    company = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    monthly_salary = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.job_title} at {self.company}"

# stores a candidates educational qualifications and details
class EducationDetail(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='education')
    qualification = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    grading_system = models.CharField(max_length=100, blank=True)
    score = models.CharField(max_length=50, blank=True)
    passing_year = models.IntegerField()

    def __str__(self):
        return f"{self.qualification} from {self.institution}"

# stores projects and related details added to a candidate's profile
class Project(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    tools_used = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.title

# stores a candidate's preferred job criteria and career preferences
class DesiredProfile(models.Model):
    profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='desired_profile')
    industry = models.CharField(max_length=255, blank=True)
    functional_role = models.CharField(max_length=255, blank=True)
    job_type = models.CharField(max_length=100, blank=True)
    preferred_locations = models.CharField(max_length=255, blank=True)
    expected_salary = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Desired Profile for {self.profile.user.username}"