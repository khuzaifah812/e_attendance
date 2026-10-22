import json
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (CourseForm, EventForm, LectureForm, PersonForm, PostForm, RoomForm, SemesterForm)
from .models import (Attendance, Course, Enrollment, Lecture, Notification, Post, Room, Semester,
                     SemesterEvent, User)
from .utils import (attendance_summary, face_distance, fmt_dt, haversine, notify, student_records)

STAFF = ('lecturer', 'coordinator', 'admin')
MANAGERS = ('coordinator', 'admin')
FACE_THRESHOLD = 0.55


def roles(*allowed):
    def deco(view):
        @login_required
        @wraps(view)
        def wrapper(request, *a, **kw):
            if request.user.effective_role not in allowed:
                messages.error(request, 'You do not have permission to open that page.')
                return redirect('dashboard')
            return view(request, *a, **kw)
        return wrapper
    return deco


def can_edit_lecture(user, lec):
    return user.effective_role in MANAGERS or (user.effective_role == 'lecturer' and lec.course.lecturer_id == user.id)


# ------------------------------------------------------------------ public pages
def landing(request):
    return render(request, 'landing.html')


def health(request):
    return HttpResponse('ok')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        role = request.POST.get('role', '')
        user = authenticate(request, username=username, password=request.POST.get('password', ''))
        if user is None:
            messages.error(request, 'Invalid registration number / ID or password.')
        elif role and user.effective_role != role:
            messages.warning(request, 'This account is not registered under the selected role. Please choose the correct role.')
        else:
            login(request, user)
            nxt = request.POST.get('next', '')
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect('dashboard')
    return render(request, 'login.html', {'next': request.GET.get('next', '')})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out safely.')
    return redirect('login')


def _person_create(request, kind, public):
    form = PersonForm(request.POST or None, kind=kind)
    if request.method == 'POST' and form.is_valid():
        u = form.save()
        pw = u.get_full_name()
        if u.email:
            try:
                send_mail('Welcome to SARS', 'Hello %s,\n\nYour SARS account is ready.\nUsername: %s\nPassword: %s (your full name)\n'
                          'Please change your password after logging in.' % (u.display_name, u.username, pw),
                          None, [u.email], fail_silently=True)
            except Exception:
                pass
        messages.success(request, '%s registered. Login username: %s | password: "%s" (the full name).' % (u.display_name, u.username, pw))
        return redirect('login' if public else ('students' if kind == 'student' else 'lecturers'))
    return render(request, 'person_form.html', {'form': form, 'kind': kind, 'public': public})


def register_student(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return _person_create(request, 'student', True)


@roles('admin', 'coordinator')
def person_add(request, kind):
    if kind == 'lecturer' and request.user.effective_role != 'admin':
        messages.error(request, 'Only the administrator can add lecturers.')
        return redirect('dashboard')
    return _person_create(request, kind, False)


# ------------------------------------------------------------------ dashboards
@login_required
def dashboard(request):
    role = request.user.effective_role
    if role == 'student':
        return render(request, 'student_dashboard.html', student_ctx(request.user))
    if role == 'admin':
        return admin_dashboard(request)
    return staff_dashboard(request)


def student_ctx(student, viewing=False):
    sem = Semester.current()
    now = timezone.now()
    summary = attendance_summary(student, sem)
    upcoming = []
    if sem:
        upcoming = list(Lecture.objects.filter(course__enrollments__student=student, course__semester=sem,
                                               cancelled=False, end__gte=now)
                        .select_related('course', 'room').order_by('start')[:6])
        done = set(Attendance.objects.filter(student=student, lecture__in=[l.id for l in upcoming]).values_list('lecture_id', flat=True))
        for l in upcoming:
            l.attended = l.id in done
    return {'student': student, 'summary': summary, 'upcoming': upcoming, 'semester': sem, 'viewing': viewing,
            'notes': Notification.objects.filter(user=student)[:5],
            'notif_total': Notification.objects.filter(user=student).count(),
            'courses_count': Enrollment.objects.filter(student=student, course__semester=sem).count()}


def staff_dashboard(request):
    user, sem, now = request.user, Semester.current(), timezone.now()
    mine = Lecture.objects.filter(course__lecturer=user, course__semester=sem).select_related('course', 'room')
    today = timezone.localdate()
    return render(request, 'staff_dashboard.html', {
        'semester': sem,
        'courses': Course.objects.filter(lecturer=user, semester=sem),
        'lectures': mine.order_by('start'),
        'today_lectures': mine.filter(start__date=today).order_by('start'),
        'taught': mine.filter(activated_at__isnull=False, cancelled=False).count(),
        'total': mine.exclude(cancelled=True).count(),
        'students_total': User.objects.filter(role='student').count(),
        'lecturers_total': User.objects.filter(role__in=['lecturer', 'coordinator']).count(),
    })


def admin_dashboard(request):
    sem, now = Semester.current(), timezone.now()
    lecs = Lecture.objects.filter(course__semester=sem) if sem else Lecture.objects.none()
    return render(request, 'admin_dashboard.html', {
        'semester': sem,
        'students_total': User.objects.filter(role='student').count(),
        'lecturers_total': User.objects.filter(role__in=['lecturer', 'coordinator']).count(),
        'courses_total': Course.objects.filter(semester=sem).count(),
        'lectures_total': lecs.exclude(cancelled=True).count(),
        'taught_total': lecs.filter(activated_at__isnull=False, cancelled=False).count(),
        'attendance_today': Attendance.objects.filter(marked_at__date=timezone.localdate()).count(),
        'upcoming': lecs.filter(cancelled=False, end__gte=now).select_related('course', 'room').order_by('start')[:6],
        'recent_students': User.objects.filter(role='student').order_by('-date_joined')[:5],
    })


# ------------------------------------------------------------------ people (students / lecturers)
@roles('admin', 'coordinator')
def people(request, kind):
    q = request.GET.get('q', '').strip()
    level = request.GET.get('level', '')
    qs = User.objects.filter(role='student') if kind == 'students' else User.objects.filter(role__in=['lecturer', 'coordinator'])
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q))
    if level and kind == 'students':
        qs = qs.filter(level=level)
    page = Paginator(qs.order_by('last_name', 'first_name'), 12).get_page(request.GET.get('page'))
    sem = Semester.current()
    if kind == 'students':
        for s in page:
            s.pct = attendance_summary(s, sem)['percent']
    return render(request, 'people.html', {'page': page, 'kind': kind, 'q': q, 'level': level, 'total': qs.count()})


@roles('admin', 'coordinator')
def student_detail(request, pk):
    student = get_object_or_404(User, pk=pk, role='student')
    return render(request, 'student_dashboard.html', student_ctx(student, viewing=True))


@roles('admin', 'coordinator')
@require_POST
def person_delete(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser or u.pk == request.user.pk or (u.role != 'student' and request.user.effective_role != 'admin'):
        messages.error(request, 'This account cannot be deleted.')
    else:
        name, back = u.display_name, ('students' if u.role == 'student' else 'lecturers')
        u.delete()
        messages.success(request, '%s was deleted.' % name)
        return redirect(back)
    return redirect('dashboard')


@login_required
def attendance_print(request, pk=None):
    if pk is None:
        student = request.user
    else:
        student = get_object_or_404(User, pk=pk, role='student')
        if request.user.pk != student.pk and request.user.effective_role not in MANAGERS:
            messages.error(request, 'You cannot print this attendance list.')
            return redirect('dashboard')
    summary, records = student_records(student)
    return render(request, 'print_attendance.html', {'student': student, 'summary': summary, 'records': records, 'now': timezone.now()})


@roles('student')
def my_attendance(request):
    summary, records = student_records(request.user)
    return render(request, 'my_attendance.html', {'summary': summary, 'records': records})


# ------------------------------------------------------------------ lectures & timetable
@login_required
def lectures(request):
    role, user, sem = request.user.effective_role, request.user, Semester.current()
    qs = Lecture.objects.filter(course__semester=sem).select_related('course', 'room', 'course__lecturer')
    scope = request.GET.get('scope', '')
    if role == 'student':
        qs = qs.filter(course__enrollments__student=user)
    elif role == 'lecturer' or (role == 'coordinator' and scope != 'all'):
        qs = qs.filter(course__lecturer=user)
    when = request.GET.get('when', 'upcoming')
    now = timezone.now()
    if when == 'upcoming':
        qs = qs.filter(end__gte=now).order_by('start')
    elif when == 'past':
        qs = qs.filter(end__lt=now).order_by('-start')
    else:
        qs = qs.order_by('start')
    items = list(qs[:150])
    if role == 'student':
        done = set(Attendance.objects.filter(student=user, lecture__in=[l.id for l in items]).values_list('lecture_id', flat=True))
        for l in items:
            l.attended = l.id in done
    for l in items:
        l.editable = role != 'student' and can_edit_lecture(user, l)
    return render(request, 'lectures.html', {'items': items, 'when': when, 'scope': scope, 'semester': sem})


@roles(*STAFF)
def lecture_form(request, pk=None):
    lec = get_object_or_404(Lecture, pk=pk) if pk else None
    if lec and not can_edit_lecture(request.user, lec):
        messages.error(request, 'You can only edit your own lectures.')
        return redirect('lectures')
    form = LectureForm(request.POST or None, instance=lec, user=request.user)
    if request.method == 'POST' and form.is_valid():
        new = lec is None
        obj = form.save()
        if obj.is_emergency and (new or not lec.is_emergency):
            notify(obj.course.students(), 'Emergency lecture: %s' % obj.course.code,
                   'An emergency lecture "%s" has been scheduled for %s. %s' % (
                       obj.topic, fmt_dt(obj.start), ('Room: %s' % obj.room) if obj.room else 'Online'),
                   kind='emergency', link='/lectures/')
        messages.success(request, 'Lecture saved to the timetable.')
        return redirect('lectures')
    return render(request, 'lecture_form.html', {'form': form, 'lec': lec})


@roles(*STAFF)
@require_POST
def lecture_cancel(request, pk):
    lec = get_object_or_404(Lecture, pk=pk)
    if can_edit_lecture(request.user, lec) and not lec.activated_at:
        lec.cancelled = True
        lec.save(update_fields=['cancelled'])
        notify(lec.course.students(), 'Lecture cancelled: %s' % lec.course.code,
               'The lecture "%s" planned for %s has been cancelled.' % (lec.topic, fmt_dt(lec.start)), kind='announcement')
        messages.success(request, 'Lecture cancelled and students notified.')
    else:
        messages.error(request, 'This lecture cannot be cancelled (it has already started or is not yours).')
    return redirect('lectures')


@roles(*STAFF)
def lecture_session(request, pk):
    lec = get_object_or_404(Lecture.objects.select_related('course', 'room'), pk=pk)
    if not can_edit_lecture(request.user, lec):
        messages.error(request, 'This is not your lecture.')
        return redirect('lectures')
    if request.method == 'POST':
        try:
            lec.activate()
            messages.success(request, 'Session activated. The code is valid for %s.' % (
                'until the lecture ends' if lec.code_expires_at == lec.end else '30 minutes'))
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
        return redirect('lecture_session', pk=pk)
    return render(request, 'session.html', {'lec': lec, 'open': lec.session_open(),
                                            'enrolled': lec.course.enrollments.count()})


@roles(*STAFF)
def api_session_attendance(request, pk):
    lec = get_object_or_404(Lecture, pk=pk)
    if not can_edit_lecture(request.user, lec):
        return JsonResponse({'ok': False}, status=403)
    rows = [{'name': a.student.display_name, 'reg': a.student.username, 'time': timezone.localtime(a.marked_at).strftime('%H:%M:%S'),
             'method': a.get_method_display()} for a in lec.attendances.select_related('student')]
    return JsonResponse({'ok': True, 'count': len(rows), 'enrolled': lec.course.enrollments.count(), 'rows': rows,
                         'open': lec.session_open()})


# ------------------------------------------------------------------ taking attendance (students)
@roles('student')
def attend_page(request, pk):
    lec = get_object_or_404(Lecture.objects.select_related('course', 'room'), pk=pk)
    enrolled = Enrollment.objects.filter(student=request.user, course=lec.course).exists()
    return render(request, 'attend.html', {
        'lec': lec, 'enrolled': enrolled, 'open': lec.session_open(),
        'already': Attendance.objects.filter(student=request.user, lecture=lec).first(),
        'has_face': bool(request.user.descriptor())})


@roles('student')
@require_POST
def api_attend(request, pk):
    user = request.user
    lec = get_object_or_404(Lecture.objects.select_related('course', 'room'), pk=pk)
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        data = {}

    def fail(msg, status=400):
        return JsonResponse({'ok': False, 'message': msg}, status=status)

    if not Enrollment.objects.filter(student=user, course=lec.course).exists():
        return fail('You are not registered for %s.' % lec.course.code, 403)
    if Attendance.objects.filter(lecture=lec, student=user).exists():
        return fail('You have already taken attendance for this lecture. It can only be taken once.')
    if not lec.session_open():
        return fail('Attendance is not active for this lecture. The lecturer must activate it, and the code lasts 30 minutes '
                    'within the lecture time.')
    code = (data.get('code') or '').strip().upper()
    distance, method = None, None
    if lec.mode == 'online':
        if code != lec.code:
            return fail('Invalid or expired code.')
        method = 'code'
    else:
        try:
            lat, lng = float(data.get('lat')), float(data.get('lng'))
        except (TypeError, ValueError):
            return fail('Your location is required. Allow location access in your browser and try again.')
        if not lec.room:
            return fail('This lecture has no room location set. Contact your lecturer.')
        distance = haversine(lat, lng, lec.room.latitude, lec.room.longitude)
        if distance > lec.room.radius_m:
            return fail('You are about %d m away from %s. You must be inside the lecture room to take attendance.'
                        % (round(distance), lec.room.name))
        if code:
            if code != lec.code:
                return fail('Invalid or expired code.')
            method = 'qr'
        elif data.get('descriptor'):
            ref = user.descriptor()
            if not ref:
                return fail('Your face is not enrolled yet. Enrol it in My Profile, or use the QR code / code from the lecturer.')
            try:
                dist = face_distance(ref, data['descriptor'])
            except (TypeError, ValueError):
                return fail('Face scan failed. Try again.')
            if dist > FACE_THRESHOLD:
                return fail('Face not recognised. Please face the camera in good light and try again.')
            method = 'face'
        else:
            return fail('Scan your face or enter the QR code / code given by the lecturer.')
    try:
        Attendance.objects.create(lecture=lec, student=user, method=method, distance_m=distance)
    except IntegrityError:
        return fail('You have already taken attendance for this lecture.')
    return JsonResponse({'ok': True, 'message': 'Attendance marked successfully for %s.' % lec.course.code,
                         'time': timezone.localtime().strftime('%d %b %Y, %H:%M'), 'method': method})


@login_required
@require_POST
def api_face_enroll(request):
    try:
        data = json.loads(request.body or '{}')
        desc = data.get('descriptor')
        if not (isinstance(desc, list) and len(desc) == 128):
            raise ValueError
        request.user.face_descriptor = json.dumps([float(x) for x in desc])
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'message': 'No clear face detected. Try again.'}, status=400)
    if str(data.get('photo', '')).startswith('data:image') and not request.user.photo_data:
        request.user.photo_data = data['photo']
    request.user.save(update_fields=['face_descriptor', 'photo_data'])
    return JsonResponse({'ok': True, 'message': 'Your face has been enrolled.'})


# ------------------------------------------------------------------ courses
@login_required
def courses(request):
    role, sem = request.user.effective_role, Semester.current()
    qs = Course.objects.filter(semester=sem).select_related('lecturer')
    if role == 'student':
        mine = set(Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True))
        items = [c for c in qs if not request.user.level or c.level == request.user.level]
        for c in items:
            c.enrolled = c.id in mine
        return render(request, 'courses_student.html', {'items': items, 'semester': sem})
    if role == 'lecturer' or (role == 'coordinator' and request.GET.get('scope') != 'all'):
        qs = qs.filter(lecturer=request.user)
    items = list(qs)
    for c in items:
        c.student_count = c.enrollments.count()
        c.taught_count = c.taught_lectures().count()
    return render(request, 'courses_staff.html', {'items': items, 'semester': sem, 'scope': request.GET.get('scope', '')})


@roles('student')
@require_POST
def course_toggle(request, pk):
    c = get_object_or_404(Course, pk=pk, semester=Semester.current())
    obj = Enrollment.objects.filter(student=request.user, course=c).first()
    if obj:
        obj.delete()
        messages.warning(request, 'You dropped %s.' % c.code)
    else:
        Enrollment.objects.create(student=request.user, course=c)
        messages.success(request, 'You are now registered for %s.' % c.code)
    return redirect('courses')


@roles(*STAFF)
def course_attendance(request, pk):
    c = get_object_or_404(Course.objects.select_related('lecturer', 'semester'), pk=pk)
    if request.user.effective_role == 'lecturer' and c.lecturer_id != request.user.id:
        messages.error(request, 'This is not your course.')
        return redirect('courses')
    taught = c.taught_lectures().count()
    rows = []
    for s in c.students():
        att = Attendance.objects.filter(student=s, lecture__course=c).count()
        rows.append({'student': s, 'attended': att, 'percent': round(att * 100 / taught) if taught else 0})
    lecs = c.lectures.filter(cancelled=False).order_by('start')
    for l in lecs:
        l.count = l.attendances.count()
    return render(request, 'course_attendance.html', {'course': c, 'rows': rows, 'taught': taught, 'lectures': lecs,
                                                      'total_students': len(rows)})


# ------------------------------------------------------------------ posts (announcements, coursework, notes, assignments)
@login_required
def posts(request):
    role = request.user.effective_role
    qs = Post.objects.select_related('course', 'author')
    if role == 'student':
        qs = qs.filter(course__enrollments__student=request.user)
    elif role == 'lecturer' or (role == 'coordinator' and request.GET.get('scope') != 'all'):
        qs = qs.filter(author=request.user)
    kind = request.GET.get('kind', '')
    if kind:
        qs = qs.filter(kind=kind)
    return render(request, 'posts.html', {'items': qs[:80], 'kind': kind, 'kinds': Post.KINDS})


@roles(*STAFF)
def post_new(request):
    form = PostForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.author = request.user
        p.save()
        due = ('\nDue: %s' % fmt_dt(p.due_date)) if p.due_date else ''
        link = request.build_absolute_uri(p.attachment.url) if p.attachment else ''
        n = notify(p.course.students(), '%s: %s (%s)' % (p.get_kind_display(), p.title, p.course.code),
                   '%s posted by %s:\n\n%s%s%s' % (p.get_kind_display(), request.user.display_name, p.body, due,
                                                  ('\n\nDownload: ' + link) if link else ''),
                   kind=p.kind, link='/posts/', attachment=p.attachment.path if p.attachment else None)
        messages.success(request, 'Posted. %d students were notified on the system and by email.' % n)
        return redirect('posts')
    return render(request, 'post_form.html', {'form': form})


# ------------------------------------------------------------------ calendar
@login_required
def calendar_page(request):
    return render(request, 'calendar.html', {'semester': Semester.current()})


@login_required
def api_calendar(request):
    sem, role = Semester.current(), request.user.effective_role
    if not sem:
        return JsonResponse({'events': []})
    ev = []
    for e in SemesterEvent.objects.filter(semester=sem):
        d, last = e.date, (e.end_date or e.date)
        while d <= last and (d - e.date).days < 120:
            ev.append({'date': d.isoformat(), 'title': e.title, 'kind': e.kind, 'time': '', 'note': e.description})
            d += timedelta(days=1)
    ev.append({'date': sem.start_date.isoformat(), 'title': 'Semester begins - Day 1', 'kind': 'registration', 'time': '', 'note': sem.name})
    ev.append({'date': sem.end_date.isoformat(), 'title': 'Semester ends', 'kind': 'holiday', 'time': '', 'note': sem.name})
    qs = Lecture.objects.filter(course__semester=sem, cancelled=False).select_related('course', 'room')
    if role == 'student':
        qs = qs.filter(course__enrollments__student=request.user)
    elif role in ('lecturer', 'coordinator'):
        qs = qs.filter(course__lecturer=request.user)
    for l in qs:
        s = timezone.localtime(l.start)
        ev.append({'date': s.date().isoformat(), 'title': '%s: %s' % (l.course.code, l.topic),
                   'kind': 'emergency' if l.is_emergency else 'lecture', 'time': s.strftime('%H:%M') + '-' + timezone.localtime(l.end).strftime('%H:%M'),
                   'note': ('Room: %s' % l.room) if l.mode == 'physical' and l.room else 'Online'})
    return JsonResponse({'start': sem.start_date.isoformat(), 'end': sem.end_date.isoformat(), 'semester': sem.name, 'events': ev})


# ------------------------------------------------------------------ notifications & profile
@login_required
def notifications(request):
    tab = request.GET.get('tab', 'system')
    qs = Notification.objects.filter(user=request.user)
    if tab == 'email':
        qs = qs.filter(emailed=True)
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'notifications.html', {'page': page, 'tab': tab})


@login_required
@require_POST
def notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')


@login_required
def profile(request):
    form = PasswordChangeForm(request.user, request.POST or None) if request.method == 'POST' else PasswordChangeForm(request.user)
    for f in form.fields.values():
        f.widget.attrs['class'] = 'input'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully.')
        return redirect('profile')
    return render(request, 'profile.html', {'form': form, 'has_face': bool(request.user.descriptor())})


# ------------------------------------------------------------------ simple CRUD for courses / rooms / semesters / events
CRUD = {
    'courses': dict(model=Course, form=CourseForm, title='Course', after='courses',
                    cols=['code', 'title', 'level', 'lecturer', 'semester']),
    'rooms': dict(model=Room, form=RoomForm, title='Room', after='crud_list',
                  cols=['name', 'building', 'latitude', 'longitude', 'radius_m']),
    'semesters': dict(model=Semester, form=SemesterForm, title='Semester', after='crud_list',
                      cols=['name', 'start_date', 'end_date', 'is_current']),
    'events': dict(model=SemesterEvent, form=EventForm, title='Semester event', after='crud_list',
                   cols=['title', 'kind', 'date', 'end_date', 'semester']),
}


def _cfg(key):
    if key not in CRUD:
        from django.http import Http404
        raise Http404
    return CRUD[key]


def _after(key, cfg):
    return redirect('courses') if cfg['after'] == 'courses' else redirect('crud_list', key=key)


@roles(*MANAGERS)
def crud_list(request, key):
    cfg = _cfg(key)
    rows = []
    for o in cfg['model'].objects.all():
        vals = []
        for f in cfg['cols']:
            disp = getattr(o, 'get_%s_display' % f, None)
            v = disp() if disp else getattr(o, f)
            vals.append('Yes' if v is True else ('No' if v is False else ('-' if v in (None, '') else v)))
        rows.append((o, vals))
    labels = [cfg['model']._meta.get_field(f).verbose_name.title() for f in cfg['cols']]
    return render(request, 'crud_list.html', {'key': key, 'cfg': cfg, 'rows': rows, 'labels': labels,
                                              'plural': cfg['model']._meta.verbose_name_plural.title()})


@roles(*MANAGERS)
def crud_form(request, key, pk=None):
    cfg = _cfg(key)
    obj = get_object_or_404(cfg['model'], pk=pk) if pk else None
    form = cfg['form'](request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '%s saved.' % cfg['title'])
        return _after(key, cfg)
    return render(request, 'crud_form.html', {'form': form, 'key': key, 'cfg': cfg, 'obj': obj})


@roles(*MANAGERS)
@require_POST
def crud_delete(request, key, pk):
    cfg = _cfg(key)
    get_object_or_404(cfg['model'], pk=pk).delete()
    messages.success(request, '%s deleted.' % cfg['title'])
    return _after(key, cfg)
