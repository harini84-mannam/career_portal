from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-of-service/", views.terms_of_service, name="terms_of_service"),
    path("support/", views.support, name="support"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("quick-screen/", views.index, name="index"),
    path("screen", views.screen, name="screen"),
    path("download/<str:which>", views.download, name="download"),

    # HR routes
    path("hr/dashboard/", views.hr_dashboard, name="hr_dashboard"),
    path("hr/jobs/new/", views.post_job, name="post_job"),
    path("hr/jobs/", views.my_jobs, name="my_jobs"),
    path("hr/applications/", views.all_applications, name="all_applications"),
    path("hr/jobs/<int:job_id>/toggle/", views.toggle_job_status, name="toggle_job_status"),
    path("hr/jobs/<int:job_id>/applicants/", views.applicant_list, name="applicant_list"),
    path("hr/applications/<int:application_id>/", views.application_detail, name="application_detail"),
    path("hr/applications/<int:application_id>/candidate-profile/", views.recruiter_candidate_profile, name="recruiter_candidate_profile"),
    path("hr/candidates/", views.talent_pool, name="talent_pool"),
    path("hr/candidates/<int:candidate_id>/", views.candidate_directory_profile, name="candidate_directory_profile"),
    path("hr/candidates/<int:candidate_id>/resume/", views.download_candidate_resume, name="download_candidate_resume"),
    path("hr/applications/<int:application_id>/status/", views.update_application_status, name="update_application_status"),
    path("hr/interviews/<int:interview_id>/status/", views.update_interview_status, name="update_interview_status"),
    path("hr/applications/<int:application_id>/schedule-interview/", views.schedule_interview, name="schedule_interview"),
    path("hr/applications/<int:application_id>/resume/", views.download_application_resume, name="download_application_resume"),


    # Candidate routes
    path("candidate/dashboard/", views.candidate_dashboard, name="candidate_dashboard"),
    path("candidate/jobs/", views.browse_jobs, name="browse_jobs"),
    path("candidate/jobs/<int:job_id>/", views.job_detail, name="job_detail"),
    path("candidate/jobs/<int:job_id>/save/", views.toggle_saved_job, name="toggle_saved_job"),
    path("candidate/jobs/<int:job_id>/apply/", views.apply_job, name="apply_job"),
    path("candidate/applications/", views.my_applications, name="my_applications"),
    path("candidate/applications/<int:application_id>/", views.candidate_application_detail, name="candidate_application_detail"),
    path("candidate/applications/<int:application_id>/offer/", views.download_candidate_offer, name="download_candidate_offer"),
    path("candidate/saved-jobs/", views.saved_jobs, name="saved_jobs"),
    path("candidate/interviews/", views.upcoming_interviews, name="upcoming_interviews"),
    path("candidate/profile/", views.profile_view), # Legacy support
    path("profile/", views.profile_view, name="profile_view"),
    path("profile/edit/", views.profile_settings, name="profile_settings"),
    path("profile/settings/", views.account_settings_view, name="account_settings"),
    path("profile/change-password/", views.change_password_view, name="change_password"),
    path("profile/notifications/", views.update_notification_preference_view, name="update_notification_preference"),
    path("profile/logout-other-sessions/", views.logout_other_sessions_view, name="logout_other_sessions"),
    path("profile/deactivate/", views.deactivate_account_view, name="deactivate_account"),
    path("profile/employment/add/", views.add_employment, name="add_employment"),
    path("profile/education/add/", views.add_education, name="add_education"),
    path("profile/project/add/", views.add_project, name="add_project"),
]