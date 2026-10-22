import json
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

LEVELS = [('certificate', 'Certificate'), ('diploma', 'Diploma'),
          ('degree', 'Degree'), ('postgraduate', 'Postgraduate')]


class User(AbstractUser):
    ROLES = [('admin', 'Administrator'), ('coordinator', 'Academic Coordinator'),
             ('lecturer', 'Lecturer'), ('student', 'Student')]
    role = models.CharField(max_length=12, choices=ROLES, default='student')
    phone = models.CharField(max_length=30, blank=True)
    gender = models.CharField(max_length=1, blank=True, choices=[('M', 'Male'), ('F', 'Female')])
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=60, blank=True, default='Ugandan')
    address = models.CharField(max_length=200, blank=True)
    district = models.CharField(max_length=80, blank=True)
    level = models.CharField(max_length=14, blank=True, choices=LEVELS)
    program = models.CharField('Program / Course of study', max_length=120, blank=True)
    faculty = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    year_of_admission = models.PositiveSmallIntegerField(null=True, blank=True)
    photo_data = models.TextField(blank=True)          # profile photo stored as a data-URL
    face_descriptor = models.TextField(blank=True)     # 128 numbers (JSON) computed in the browser

    def save(self, *args, **kwargs):
        if self.is_superuser and self.role == 'student':
            self.role = 'admin'
        super().save(*args, **kwargs)

    @property
    def effective_role(self):
        return 'admin' if self.is_superuser else self.role

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

    @property
    def initials(self):
        return ''.join(p[0] for p in self.display_name.split()[:2]).upper() or '?'

    def descriptor(self):
        try:
            d = json.loads(self.face_descriptor or '[]')
            return d if isinstance(d, list) and len(d) == 128 else None
        except (ValueError, TypeError):
            return None

    def __str__(self):
        return '%s (%s)' % (self.display_name, self.username)


class Semester(models.Model):
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            Semester.objects.exclude(pk=self.pk).update(is_current=False)

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).first() or cls.objects.order_by('-start_date').first()

    def __str__(self):
        return self.name


class Course(models.Model):
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=150)
    level = models.CharField(max_length=14, choices=LEVELS, default='diploma')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='courses')
    lecturer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='courses_taught')

    class Meta:
        unique_together = ('code', 'semester')
        ordering = ['code']

    def taught_lectures(self):
        return self.lectures.filter(activated_at__isnull=False, cancelled=False)

    def students(self):
        return User.objects.filter(enrollments__course=self).order_by('last_name', 'first_name')

    def __str__(self):
        return '%s - %s' % (self.code, self.title)


class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')


class Room(models.Model):
    name = models.CharField(max_length=80)
    building = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(help_text='GPS latitude of the room, e.g. 0.3476')
    longitude = models.FloatField(help_text='GPS longitude of the room, e.g. 32.5825')
    radius_m = models.PositiveIntegerField('Allowed radius (metres)', default=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return '%s%s' % (self.name, (' - ' + self.building) if self.building else '')


class Lecture(models.Model):
    MODES = [('physical', 'Physical'), ('online', 'Online')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lectures')
    topic = models.CharField(max_length=200)
    mode = models.CharField(max_length=10, choices=MODES, default='physical')
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)
    meeting_link = models.URLField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    is_emergency = models.BooleanField('Emergency lecture', default=False)
    cancelled = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    code = models.CharField(max_length=8, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['start']

    # ---------- validation: no two lectures at the same time ----------
    def clean(self):
        if not (self.start and self.end and self.course_id):
            return
        if self.end <= self.start:
            raise ValidationError('The end time must be after the start time.')
        if self.mode == 'physical' and not self.room_id:
            raise ValidationError('Select a room for a physical lecture.')
        sem = self.course.semester
        if not (sem.start_date <= timezone.localtime(self.start).date() <= sem.end_date):
            raise ValidationError('The lecture date must be inside the semester (%s to %s).' % (sem.start_date, sem.end_date))
        overlap = Lecture.objects.filter(cancelled=False, start__lt=self.end, end__gt=self.start).exclude(pk=self.pk)
        if self.course.lecturer_id:
            clash = overlap.filter(course__lecturer_id=self.course.lecturer_id).first()
            if clash:
                raise ValidationError('Schedule clash: %s already has "%s" (%s) from %s to %s.' % (
                    self.course.lecturer.display_name, clash.topic, clash.course.code,
                    timezone.localtime(clash.start).strftime('%d %b %H:%M'), timezone.localtime(clash.end).strftime('%H:%M')))
        if self.mode == 'physical' and self.room_id:
            clash = overlap.filter(room_id=self.room_id).first()
            if clash:
                raise ValidationError('Room clash: %s is already booked for %s at that time.' % (self.room.name, clash.course.code))

    # ---------- state helpers ----------
    @property
    def lecturer(self):
        return self.course.lecturer

    @property
    def state(self):
        now = timezone.now()
        if self.cancelled:
            return 'cancelled'
        if now < self.start:
            return 'upcoming'
        if now <= self.end:
            return 'live'
        return 'ended'

    @property
    def taught(self):
        return self.activated_at is not None and not self.cancelled

    def session_open(self, now=None):
        now = now or timezone.now()
        return bool(self.activated_at and self.code_expires_at and not self.cancelled
                    and self.start <= now <= self.end and now <= self.code_expires_at)

    def activate(self):
        """Lecturer starts the session: creates a code valid for 30 minutes (never beyond the lecture end)."""
        now = timezone.now()
        if self.cancelled:
            raise ValidationError('This lecture was cancelled.')
        if now < self.start:
            raise ValidationError('The session can only be activated once the lecture time has started (%s).'
                                  % timezone.localtime(self.start).strftime('%H:%M'))
        if now > self.end:
            raise ValidationError('This lecture has already ended.')
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        self.code = ''.join(secrets.choice(alphabet) for _ in range(6))
        if not self.activated_at:
            self.activated_at = now
        self.code_expires_at = min(now + timedelta(minutes=30), self.end)
        self.save(update_fields=['code', 'activated_at', 'code_expires_at'])

    def __str__(self):
        return '%s - %s (%s)' % (self.course.code, self.topic, timezone.localtime(self.start).strftime('%d %b %H:%M'))


class Attendance(models.Model):
    METHODS = [('face', 'Face recognition'), ('qr', 'QR code'), ('code', 'Online code')]
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    marked_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=10, choices=METHODS)
    distance_m = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('lecture', 'student')      # a student can mark a lecture only once
        ordering = ['marked_at']


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    kind = models.CharField(max_length=20, default='system')
    link = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


class ReminderLog(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    minutes = models.PositiveIntegerField()

    class Meta:
        unique_together = ('lecture', 'user', 'minutes')


class Post(models.Model):
    KINDS = [('announcement', 'Announcement'), ('coursework', 'Coursework'),
             ('notes', 'Lecture notes'), ('assignment', 'Assignment')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    kind = models.CharField(max_length=14, choices=KINDS, default='announcement')
    title = models.CharField(max_length=200)
    body = models.TextField()
    attachment = models.FileField(upload_to='posts/', blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SemesterEvent(models.Model):
    KINDS = [('registration', 'Registration'), ('lectures', 'Lectures'), ('assignment', 'Assignment / Coursework'),
             ('exam', 'Examination'), ('meeting', 'Meeting'), ('holiday', 'Holiday / Break'),
             ('emergency', 'Emergency lecture'), ('other', 'Other')]
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=150)
    kind = models.CharField(max_length=14, choices=KINDS, default='other')
    date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return '%s (%s)' % (self.title, self.date)
