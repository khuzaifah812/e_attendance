from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . import models

@admin.register(models.User)
class SarsUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('SARS', {'fields': ('role', 'phone', 'gender', 'date_of_birth', 'nationality', 'address',
                                                           'district', 'level', 'program', 'faculty', 'department', 'year_of_admission')}),)
    list_display = ('username', 'first_name', 'last_name', 'role', 'email')
    list_filter = ('role', 'level')

for m in (models.Semester, models.Course, models.Enrollment, models.Room, models.Lecture, models.Attendance,
          models.Notification, models.Post, models.SemesterEvent):
    admin.site.register(m)
