import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (Attendance, Course, Enrollment, Lecture, Post, Room, Semester, SemesterEvent, User)


def mk(username, first, last, role, email, **extra):
    u, created = User.objects.get_or_create(username=username, defaults=dict(
        first_name=first, last_name=last, role=role, email=email, **extra))
    if created:
        u.set_password('%s %s' % (first, last))
        u.save()
    return u


class Command(BaseCommand):
    help = 'Create demo data: semester, rooms, users, courses, lectures (one is LIVE now), events.'

    def add_arguments(self, parser):
        parser.add_argument('--lat', type=float, default=0.3476, help='latitude of your test room (default Kampala)')
        parser.add_argument('--lng', type=float, default=32.5825, help='longitude of your test room')
        parser.add_argument('--email', default='', help='your real email so reminders reach you')

    def handle(self, *a, **o):
        now = timezone.now()
        today = timezone.localdate()
        sem, _ = Semester.objects.get_or_create(name='Semester I 2026/2027', defaults=dict(
            start_date=today - timedelta(days=40), end_date=today + timedelta(days=75), is_current=True))
        sem.is_current = True
        sem.save()

        hall, _ = Room.objects.get_or_create(name='Lecture Hall 101', defaults=dict(
            building='Block A', address='UICT Main Campus', latitude=o['lat'], longitude=o['lng'], radius_m=150))
        lab, _ = Room.objects.get_or_create(name='ICT Lab 2', defaults=dict(
            building='Block B', address='UICT Main Campus', latitude=o['lat'], longitude=o['lng'], radius_m=150))

        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser('admin', o['email'] or 'admin@sars.local', 'Admin@123',
                                                  first_name='Michael', last_name='Okello', role='admin')
        coord = mk('COORD01', 'Grace', 'Nakato', 'coordinator', o['email'] or 'coord@sars.local', department='Academic Registry')
        lec1 = mk('LEC001', 'Sarah', 'Ndagire', 'lecturer', o['email'] or 'sarah@sars.local', department='Computing')
        lec2 = mk('LEC002', 'Peter', 'Ssemwogerere', 'lecturer', o['email'] or 'peter@sars.local', department='Mathematics')
        lec3 = mk('LEC003', 'Joan', 'Atim', 'lecturer', o['email'] or 'joan@sars.local', department='Data Science')

        names = [('Francis', 'Musimbi'), ('Sarah', 'Nalubega'), ('David', 'Kato'), ('Aisha', 'Nanyonga'),
                 ('John', 'Bosco'), ('Mary', 'Achieng'), ('Brian', 'Mugisha'), ('Esther', 'Namatovu')]
        students = []
        for i, (f, l) in enumerate(names, 1):
            students.append(mk('2026/%04d' % i, f, l, 'student', o['email'] or ('%s.%s@students.sars.local' % (f.lower(), l.lower())),
                               gender='F' if f in ('Sarah', 'Aisha', 'Mary', 'Esther') else 'M', level='diploma',
                               program='Software Engineering', faculty='ICT', year_of_admission=2025, nationality='Ugandan',
                               district='Kampala', phone='+256700000%03d' % i))

        specs = [('CSC101', 'Introduction to Computer Science', lec1), ('MAT201', 'Discrete Mathematics', lec2),
                 ('DSS301', 'Data Analytics', lec3), ('ICT101', 'ICT Fundamentals', coord)]
        courses = []
        for code, title, lec in specs:
            c, _ = Course.objects.get_or_create(code=code, semester=sem, defaults=dict(title=title, level='diploma', lecturer=lec))
            courses.append(c)
            for s in students:
                Enrollment.objects.get_or_create(student=s, course=c)

        if not Lecture.objects.exists():
            random.seed(7)
            # past lectures (already taught) - each course on a different hour so nobody clashes
            for ci, c in enumerate(courses):
                for w in range(1, 7):
                    day = today - timedelta(days=w * 6 - ci)
                    start = timezone.make_aware(datetime(day.year, day.month, day.day, 8 + ci * 2, 0))
                    lec = Lecture.objects.create(course=c, topic='%s - Week %d' % (c.title, 7 - w), mode='physical', room=hall,
                                                 start=start, end=start + timedelta(hours=2), activated_at=start + timedelta(minutes=5),
                                                 code='DEMO%02d' % w, code_expires_at=start + timedelta(minutes=35))
                    for s in students:
                        if random.random() < 0.8:
                            Attendance.objects.create(lecture=lec, student=s, method=random.choice(['face', 'qr']), distance_m=20)
            # LIVE physical lecture right now (CSC101) - not yet activated
            Lecture.objects.create(course=courses[0], topic='Live demo: Algorithms & Flowcharts', mode='physical', room=hall,
                                   start=now - timedelta(minutes=10), end=now + timedelta(minutes=110))
            # LIVE online lecture right now (MAT201)
            Lecture.objects.create(course=courses[1], topic='Live demo: Propositional Logic (online)', mode='online',
                                   meeting_link='https://meet.google.com/', start=now - timedelta(minutes=5), end=now + timedelta(minutes=115))
            # upcoming: starts in ~1h05 so 1-hour and 10-minute reminders can be seen
            Lecture.objects.create(course=courses[2], topic='Regression Basics', mode='physical', room=lab,
                                   start=now + timedelta(minutes=65), end=now + timedelta(minutes=185))
            tomorrow = today + timedelta(days=1)
            for ci, c in enumerate(courses):
                st = timezone.make_aware(datetime(tomorrow.year, tomorrow.month, tomorrow.day, 8 + ci * 2, 0))
                Lecture.objects.create(course=c, topic='%s - Next topic' % c.title, mode='physical', room=hall, start=st, end=st + timedelta(hours=2))
            # emergency lecture (counts towards attendance too)
            d2 = today + timedelta(days=3)
            st = timezone.make_aware(datetime(d2.year, d2.month, d2.day, 16, 0))
            Lecture.objects.create(course=courses[3], topic='Emergency revision session', mode='online', is_emergency=True,
                                   start=st, end=st + timedelta(hours=1))

        if not SemesterEvent.objects.exists():
            ev = [('Registration & orientation', 'registration', -40, -36), ('Coursework 1 deadline', 'assignment', -15, None),
                  ('Mid-semester break', 'holiday', -8, -6), ('Lecturers meeting', 'meeting', 4, None),
                  ('Coursework 2 deadline', 'assignment', 20, None), ('End of semester examinations', 'exam', 55, 70)]
            for t, k, a, b in ev:
                SemesterEvent.objects.create(semester=sem, title=t, kind=k, date=today + timedelta(days=a),
                                             end_date=(today + timedelta(days=b)) if b is not None else None)

        if not Post.objects.exists():
            Post.objects.create(course=courses[0], author=lec1, kind='announcement', title='Welcome to CSC101',
                                body='Please bring your laptops to the next lecture.')

        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        self.stdout.write('Admin        : admin / Admin@123')
        self.stdout.write('Coordinator  : COORD01 / Grace Nakato')
        self.stdout.write('Lecturers    : LEC001 / Sarah Ndagire | LEC002 / Peter Ssemwogerere | LEC003 / Joan Atim')
        self.stdout.write('Students     : 2026/0001 / Francis Musimbi | 2026/0002 / Sarah Nalubega | ... (password = full name)')
