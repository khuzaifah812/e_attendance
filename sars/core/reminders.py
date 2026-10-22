from datetime import timedelta

from django.utils import timezone

from .models import Lecture, ReminderLog, User
from .utils import notify, fmt_dt

# minutes before the lecture -> label ; window (minutes) in which the reminder may still be sent
STUDENT_OFFSETS = [(300, '5 hours', 20), (60, '1 hour', 15), (10, '10 minutes', 8)]
STAFF_OFFSETS = [(120, '2 hours', 20), (10, '10 minutes', 8)]


def _send(lecture, users, offset, label):
    done = set(ReminderLog.objects.filter(lecture=lecture, minutes=offset).values_list('user_id', flat=True))
    todo = [u for u in users if u.id not in done]
    if not todo:
        return 0
    where = ('Room: %s' % lecture.room) if lecture.mode == 'physical' and lecture.room else 'Online lecture'
    text = '%s "%s" starts in %s (%s). %s.' % (lecture.course.code, lecture.topic, label, fmt_dt(lecture.start), where)
    if lecture.is_emergency:
        text = 'EMERGENCY LECTURE - ' + text
    ReminderLog.objects.bulk_create([ReminderLog(lecture=lecture, user=u, minutes=offset) for u in todo], ignore_conflicts=True)
    return notify(todo, 'Lecture reminder: %s in %s' % (lecture.course.code, label), text, kind='reminder', link='/lectures/')


def send_due_reminders(now=None):
    now = now or timezone.now()
    lectures = (Lecture.objects.filter(cancelled=False, start__gt=now, start__lte=now + timedelta(hours=5, minutes=2))
                .select_related('course', 'course__lecturer', 'room'))
    sent = 0
    for lec in lectures:
        left = (lec.start - now).total_seconds() / 60.0
        students = list(User.objects.filter(enrollments__course=lec.course))
        for offset, label, grace in STUDENT_OFFSETS:
            if offset - grace < left <= offset:
                sent += _send(lec, students, offset, label)
        lecturer = lec.course.lecturer
        if lecturer:
            for offset, label, grace in STAFF_OFFSETS:
                if offset - grace < left <= offset:
                    sent += _send(lec, [lecturer], offset, label)
    return sent
