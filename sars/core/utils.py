import math
import threading

from django.core import mail
from django.utils import timezone

from .models import Attendance, Course, Lecture, Notification, Semester


def haversine(lat1, lon1, lat2, lon2):
    """Distance in metres between two GPS points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def face_distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def fmt_dt(dt):
    return timezone.localtime(dt).strftime('%a %d %b %Y, %H:%M')


def _send_async(messages):
    def run():
        try:
            conn = mail.get_connection(fail_silently=True)
            conn.send_messages(messages)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def notify(users, title, message, kind='system', link='', email=True, attachment=None):
    """Create an in-system notification AND an email for every user in the list."""
    users = list(users)
    if not users:
        return 0
    Notification.objects.bulk_create([
        Notification(user=u, title=title, message=message, kind=kind, link=link, emailed=bool(email and u.email))
        for u in users])
    if email:
        msgs = []
        for u in users:
            if not u.email:
                continue
            m = mail.EmailMessage(
                subject='[SARS] ' + title,
                body='Hello %s,\n\n%s\n\n-- SARS, Students Attendance & Registration System' % (u.display_name, message),
                to=[u.email])
            if attachment:
                try:
                    m.attach_file(attachment)
                except Exception:
                    pass
            msgs.append(m)
        if msgs:
            _send_async(msgs)
    return len(users)


def attendance_summary(student, semester=None):
    """Attendance % = lectures attended / lectures actually taught (incl. emergency lectures) in the semester."""
    semester = semester or Semester.current()
    rows, tot_taught, tot_att = [], 0, 0
    if semester:
        for c in Course.objects.filter(enrollments__student=student, semester=semester).select_related('lecturer'):
            taught = c.taught_lectures().count()
            att = Attendance.objects.filter(student=student, lecture__course=c).count()
            pct = round(att * 100 / taught) if taught else 0
            rows.append({'course': c, 'taught': taught, 'attended': att, 'missed': max(taught - att, 0), 'percent': pct})
            tot_taught += taught
            tot_att += att
    pct = round(tot_att * 100 / tot_taught) if tot_taught else 0
    return {'rows': rows, 'taught': tot_taught, 'attended': tot_att, 'missed': max(tot_taught - tot_att, 0),
            'percent': pct, 'semester': semester}


def student_records(student, semester=None):
    """Every lecture taught so far for the student's courses, flagged present/absent."""
    semester = semester or Semester.current()
    summary = attendance_summary(student, semester)
    records = []
    if semester:
        lectures = list(Lecture.objects.filter(course__enrollments__student=student, course__semester=semester,
                                               activated_at__isnull=False, cancelled=False)
                        .select_related('course', 'room').order_by('start'))
        att = {a.lecture_id: a for a in Attendance.objects.filter(student=student, lecture__in=lectures)}
        for l in lectures:
            records.append({'lecture': l, 'att': att.get(l.id)})
    return summary, records
