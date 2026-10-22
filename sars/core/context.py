from django.urls import reverse
from .icons import svg
from .models import Notification

STAFF = ('lecturer', 'coordinator', 'admin')
MANAGERS = ('coordinator', 'admin')


def _menu(role):
    crud = lambda k: reverse('crud_list', kwargs={'key': k})
    dash = ('Dashboard', reverse('dashboard'), 'grid')
    cal = ('Calendar', reverse('calendar'), 'calendar')
    notif = ('Notifications', reverse('notifications'), 'bell')
    prof = ('My Profile', reverse('profile'), 'user')
    if role == 'student':
        return [dash, ('My Attendance', reverse('my_attendance'), 'check'), ('Lectures', reverse('lectures'), 'clock'), cal,
                ('My Courses', reverse('courses'), 'book'), ('Coursework & Notes', reverse('posts'), 'file'), notif, prof]
    if role == 'lecturer':
        return [dash, ('My Lectures', reverse('lectures'), 'clock'), ('Courses & Attendance', reverse('courses'), 'book'),
                ('Post Material', reverse('posts'), 'send'), cal, notif, prof]
    if role == 'coordinator':
        return [dash, ('Lectures', reverse('lectures'), 'clock'), ('Courses', reverse('courses'), 'book'),
                ('Students', reverse('students'), 'users'), ('Lecturers', reverse('lecturers'), 'user'),
                ('Post Material', reverse('posts'), 'send'), ('Rooms', crud('rooms'), 'pin'),
                ('Semester Events', crud('events'), 'layers'), cal, notif, prof]
    return [dash, ('Students', reverse('students'), 'users'), ('Lecturers', reverse('lecturers'), 'user'),
            ('Courses', reverse('courses'), 'book'), ('Timetable', reverse('lectures'), 'clock'),
            ('Rooms', crud('rooms'), 'pin'), ('Semesters', crud('semesters'), 'layers'),
            ('Semester Events', crud('events'), 'calendar'), ('Posts', reverse('posts'), 'file'),
            cal, notif, prof, ('Django Admin', '/admin/', 'shield')]


def globals(request):
    u = request.user
    if not u.is_authenticated:
        return {}
    role = u.effective_role
    unread = Notification.objects.filter(user=u, is_read=False).count()
    menu = []
    for label, url, icon in _menu(role):
        active = request.path == url if url == reverse('dashboard') else request.path.startswith(url)
        menu.append({'label': label, 'url': url, 'svg': svg(icon), 'active': active,
                     'badge': unread if label == 'Notifications' and unread else 0})
    return {'menu': menu, 'unread_count': unread, 'role': role,
            'can_manage': role in MANAGERS, 'is_staff_user': role in STAFF}
