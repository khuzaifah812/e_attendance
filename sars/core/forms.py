from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import Course, Lecture, Post, Room, Semester, SemesterEvent, User, LEVELS


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, **kw):
        kw.setdefault('format', '%Y-%m-%d')
        super().__init__(**kw)


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def __init__(self, **kw):
        kw.setdefault('format', '%Y-%m-%dT%H:%M')
        super().__init__(**kw)


class PersonForm(forms.ModelForm):
    reg_no = forms.CharField(label='Registration number (username)', max_length=40)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'date_of_birth', 'nationality', 'phone', 'address',
                  'district', 'level', 'program', 'faculty', 'department', 'year_of_admission',
                  'photo_data', 'face_descriptor']
        widgets = {'date_of_birth': DateInput(), 'photo_data': forms.HiddenInput(), 'face_descriptor': forms.HiddenInput()}

    def __init__(self, *args, kind='student', **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        for f in ('first_name', 'last_name', 'email'):
            self.fields[f].required = True
        if kind == 'student':
            for f in ('level', 'program', 'gender'):
                self.fields[f].required = True
            del self.fields['department']
        else:
            self.fields['reg_no'].label = 'Staff ID (username)'
            for f in ('level', 'program', 'year_of_admission'):
                del self.fields[f]

    def clean_reg_no(self):
        v = self.cleaned_data['reg_no'].strip()
        if User.objects.filter(username__iexact=v).exists():
            raise forms.ValidationError('This number/ID is already registered.')
        return v

    def save(self, commit=True):
        u = super().save(commit=False)
        u.username = self.cleaned_data['reg_no']
        u.role = self.kind
        u.set_password(('%s %s' % (u.first_name, u.last_name)).strip())   # default password = the person's name
        if commit:
            u.save()
        return u


class LectureForm(forms.ModelForm):
    class Meta:
        model = Lecture
        fields = ['course', 'topic', 'mode', 'room', 'meeting_link', 'start', 'end', 'is_emergency']
        widgets = {'start': DateTimeInput(), 'end': DateTimeInput()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        sem = Semester.current()
        qs = Course.objects.filter(semester=sem)
        if user and user.effective_role == 'lecturer':
            qs = qs.filter(lecturer=user)
        self.fields['course'].queryset = qs
        self.fields['room'].required = False
        self.fields['meeting_link'].required = False


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'title', 'level', 'semester', 'lecturer']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lecturer'].queryset = User.objects.filter(role__in=['lecturer', 'coordinator'])
        cur = Semester.current()
        if cur and not self.instance.pk:
            self.fields['semester'].initial = cur


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'building', 'address', 'latitude', 'longitude', 'radius_m']


class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {'start_date': DateInput(), 'end_date': DateInput()}


class EventForm(forms.ModelForm):
    class Meta:
        model = SemesterEvent
        fields = ['semester', 'title', 'kind', 'date', 'end_date', 'description']
        widgets = {'date': DateInput(), 'end_date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cur = Semester.current()
        if cur and not self.instance.pk:
            self.fields['semester'].initial = cur


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['course', 'kind', 'title', 'body', 'attachment', 'due_date']
        widgets = {'due_date': DateTimeInput(), 'body': forms.Textarea(attrs={'rows': 6})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Course.objects.filter(semester=Semester.current())
        if user and user.effective_role == 'lecturer':
            qs = qs.filter(lecturer=user)
        self.fields['course'].queryset = qs
        self.fields['due_date'].required = False
        self.fields['attachment'].required = False
