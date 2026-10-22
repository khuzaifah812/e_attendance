from django.urls import path
from . import views as v

urlpatterns = [
    path('', v.landing, name='landing'),
    path('health/', v.health, name='health'),
    path('login/', v.login_view, name='login'),
    path('logout/', v.logout_view, name='logout'),
    path('register/', v.register_student, name='register'),
    path('dashboard/', v.dashboard, name='dashboard'),

    path('students/', v.people, {'kind': 'students'}, name='students'),
    path('lecturers/', v.people, {'kind': 'lecturers'}, name='lecturers'),
    path('students/add/', v.person_add, {'kind': 'student'}, name='student_add'),
    path('lecturers/add/', v.person_add, {'kind': 'lecturer'}, name='lecturer_add'),
    path('students/<int:pk>/', v.student_detail, name='student_detail'),
    path('students/<int:pk>/print/', v.attendance_print, name='student_print'),
    path('people/<int:pk>/delete/', v.person_delete, name='person_delete'),

    path('my-attendance/', v.my_attendance, name='my_attendance'),
    path('my-attendance/print/', v.attendance_print, name='my_print'),

    path('lectures/', v.lectures, name='lectures'),
    path('lectures/new/', v.lecture_form, name='lecture_new'),
    path('lectures/<int:pk>/edit/', v.lecture_form, name='lecture_edit'),
    path('lectures/<int:pk>/cancel/', v.lecture_cancel, name='lecture_cancel'),
    path('lectures/<int:pk>/session/', v.lecture_session, name='lecture_session'),
    path('lectures/<int:pk>/attend/', v.attend_page, name='attend'),
    path('api/lectures/<int:pk>/attend/', v.api_attend, name='api_attend'),
    path('api/lectures/<int:pk>/attendance/', v.api_session_attendance, name='api_session'),
    path('api/face/enroll/', v.api_face_enroll, name='api_face_enroll'),
    path('api/calendar/', v.api_calendar, name='api_calendar'),

    path('courses/', v.courses, name='courses'),
    path('courses/<int:pk>/toggle/', v.course_toggle, name='course_toggle'),
    path('courses/<int:pk>/attendance/', v.course_attendance, name='course_attendance'),

    path('posts/', v.posts, name='posts'),
    path('posts/new/', v.post_new, name='post_new'),
    path('calendar/', v.calendar_page, name='calendar'),
    path('notifications/', v.notifications, name='notifications'),
    path('notifications/read/', v.notifications_read, name='notifications_read'),
    path('profile/', v.profile, name='profile'),

    path('manage/<str:key>/', v.crud_list, name='crud_list'),
    path('manage/<str:key>/new/', v.crud_form, name='crud_new'),
    path('manage/<str:key>/<int:pk>/edit/', v.crud_form, name='crud_edit'),
    path('manage/<str:key>/<int:pk>/delete/', v.crud_delete, name='crud_delete'),
]
