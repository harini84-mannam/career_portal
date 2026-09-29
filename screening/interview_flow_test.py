import os
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_screening.settings')

import django
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from screening.models import Application, Interview

hr = User.objects.filter(username='smoke_hr').first() or User.objects.filter(is_staff=True).first()
if hr is None:
    raise SystemExit('No HR test account found.')

application = (
    Application.objects
    .filter(job__posted_by=hr)
    .select_related('candidate__user', 'job')
    .order_by('-id')
    .first()
)
if application is None:
    raise SystemExit('No application belonging to the HR account was found.')

application.status = 'hired'
application.save(update_fields=['status', 'updated_at'])

candidate = application.candidate.user
client = Client()
client.force_login(hr)

scheduled_at = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)
response = client.post(
    reverse('schedule_interview', args=[application.id]),
    {
        'scheduled_at': scheduled_at.strftime('%Y-%m-%dT%H:%M'),
        'location': 'https://meet.google.com/meslova-test',
        'notes': 'Please join five minutes early.',
    },
)
assert response.status_code == 302, response.status_code

interview = Interview.objects.filter(application=application, status='scheduled').latest('id')
assert interview.location == 'https://meet.google.com/meslova-test'

client.force_login(candidate)
response = client.get(reverse('my_applications'))
assert response.status_code == 200, response.status_code
assert b'Interview scheduled' in response.content
assert b'meslova-test' in response.content

print('INTERVIEW_FLOW_OK')
print({
    'candidate': candidate.username,
    'job': application.job.title,
    'application_id': application.id,
    'application_status': application.status,
    'interview_id': interview.id,
    'scheduled_at': interview.scheduled_at.isoformat(),
    'location': interview.location,
})

# Leave the smoke record in a clean state for another website test.
interview.delete()
application.status = 'applied'
application.save(update_fields=['status', 'updated_at'])
print('SMOKE_INTERVIEW_RECORD_CLEANED')
