
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.views import View

from accounts.forms import FacultyLecturerEditForm
from django.views.generic import UpdateView
from django_filters.views import FilterView

# App Imports
from accounts.models import User, Student
from accounts.forms import StaffAddForm, FacultyLecturerAddForm
from accounts.filters import LecturerFilter, StudentFilter
from accounts.decorators import faculty_admin_required

from course.models import Program, Course, CourseAllocation
from course.forms import (
    ProgramForm, CourseAddForm,
    CourseAllocationForm, EditCourseAllocationForm
)


from django.views.generic import CreateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.crypto import get_random_string
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings

from accounts.models import User
from accounts.forms import FacultyLecturerAddForm
from accounts.decorators import faculty_admin_required

from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa  # make sure this is installed
from audit.utils import log_activity
from core.models import SiteSettings
from core.pdf_utils import pdf_link_callback

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyProgramListView(ListView):
    model = Program
    template_name = 'faculty_admin/program_list.html'
    context_object_name = 'programs'

    def get_queryset(self):
        return Program.objects.filter(faculty=self.request.user.faculty)


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyProgramCreateView(CreateView):
    model = Program
    form_class = ProgramForm
    template_name = 'faculty_admin/program_add.html'
    success_url = reverse_lazy('faculty_program_list')

    def form_valid(self, form):
        form.instance.faculty = self.request.user.faculty
        messages.success(self.request, "Program added successfully.")
        return super().form_valid(form)
@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyProgramEditView(UpdateView):
    model = Program
    form_class = ProgramForm
    template_name = 'faculty_admin/program_add.html'
    success_url = reverse_lazy('faculty_program_list')

    def dispatch(self, request, *args, **kwargs):
        program = self.get_object()
        if program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyProgramDetailView(DetailView):
    model = Program
    template_name = 'faculty_admin/program_single.html'
    context_object_name = 'program'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['courses'] = Course.objects.filter(program=self.object)
        return context

    def dispatch(self, request, *args, **kwargs):
        program = self.get_object()
        if program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)


class FacultyCourseAddView(CreateView):
    model = Course
    form_class = CourseAddForm

    template_name = 'faculty_admin/course_add.html'

    def dispatch(self, request, *args, **kwargs):
        self.program = get_object_or_404(Program, pk=kwargs['pk'])
        if self.program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['program'] = self.program
        return kwargs

    def form_valid(self, form):
        form.instance.program = self.program
        messages.success(self.request, "Course added successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('faculty_program_detail', kwargs={'pk': self.program.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['program'] = self.program
        context['title'] = "Add Course"
        return context
    


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyCourseListView(TemplateView):
    template_name = 'faculty_admin/course_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        faculty = self.request.user.faculty
        programs = Program.objects.filter(faculty=faculty).prefetch_related('course_set')
        context['programs'] = programs
        return context


# @method_decorator([login_required, faculty_admin_required], name='dispatch')
# class FacultyCourseAddView(CreateView):
#     model = Course
#     form_class = CourseAddForm
#     template_name = 'faculty_admin/course_add.html'

#     def dispatch(self, request, *args, **kwargs):
#         self.program = get_object_or_404(Program, pk=kwargs['pk'])
#         if self.program.faculty != request.user.faculty:
#             return redirect('permission_denied')
#         return super().dispatch(request, *args, **kwargs)

#     def form_valid(self, form):
#         form.instance.program = self.program
#         messages.success(self.request, "Course added successfully.")
#         return super().form_valid(form)

#     def get_success_url(self):
#         return reverse_lazy('faculty_program_detail', kwargs={'pk': self.program.pk})

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['program'] = self.program
#         return context


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyCourseEditView(UpdateView):
    model = Course
    form_class = CourseAddForm
    template_name = 'faculty_admin/course_edit.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def dispatch(self, request, *args, **kwargs):
        course = self.get_object()
        if course.program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('faculty_program_detail', kwargs={'pk': self.object.program.pk})


# @method_decorator([login_required, faculty_admin_required], name='dispatch')
# class FacultyCourseListView(ListView):
#     model = Course
#     template_name = 'faculty_admin/course_list.html'
#     context_object_name = 'courses'

#     def get_queryset(self):
#         return Course.objects.filter(program__faculty=self.request.user.faculty)


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyLecturerListView(FilterView):
    model = User
    template_name = 'faculty_admin/lecturer_list.html'
    filterset_class = LecturerFilter
    context_object_name = 'filter'

    def get_queryset(self):
        return User.objects.filter(is_lecturer=True, faculty=self.request.user.faculty)

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class AddLecturerView(CreateView):
    model = User
    form_class = StaffAddForm
    template_name = 'faculty_admin/add_staff.html'
    success_url = reverse_lazy('lecturer_list')

    def form_valid(self, form):
        # Set lecturer and assign current faculty
        form.instance.is_lecturer = True
        form.instance.faculty = self.request.user.faculty
        messages.success(self.request, f"Lecturer {form.instance.get_full_name} added successfully.")
        return super().form_valid(form)

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        # Restrict faculty dropdown to the one of current admin (optional)
        form.fields['faculty'].queryset = Faculty.objects.filter(id=self.request.user.faculty.id)
        form.fields['faculty'].initial = self.request.user.faculty
        form.fields['faculty'].widget.attrs['readonly'] = True
        return form

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyStudentListView(FilterView):
    model = Student
    template_name = 'faculty_admin/student_list.html'
    filterset_class = StudentFilter
    context_object_name = 'filter'

    def get_queryset(self):
        return Student.objects.filter(program__faculty=self.request.user.faculty)

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyStudentByProgramView(TemplateView):
    template_name = 'faculty_admin/students_by_program.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        faculty = self.request.user.faculty
        # Ensure prefetching students under each program
        context['programs'] = Program.objects.filter(faculty=faculty).prefetch_related('student_set')
        return context


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyUserCourseListView(TemplateView):
    template_name = 'faculty_admin/user_course_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['courses'] = Course.objects.filter(program__faculty=self.request.user.faculty)
        return context


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class CourseAllocationListView(ListView):
    model = CourseAllocation
    template_name = 'faculty_admin/course_allocation_view.html'
    context_object_name = 'filter'

    def get_queryset(self):
        qs = CourseAllocation.objects.filter(courses__program__faculty=self.request.user.faculty).distinct()
        print("User:", self.request.user)
        print("User Faculty:", self.request.user.faculty)
        print("Allocations Found:", qs.count())
        for alloc in qs:
            print("Lecturer:", alloc.lecturer)
            print("Courses:", list(alloc.courses.all()))
        return qs

class CourseAllocationForm(forms.ModelForm):
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),  # initially none
        widget=forms.CheckboxSelectMultiple(attrs={"class": "browser-default checkbox"}),
        required=True,
    )
    lecturer = forms.ModelChoiceField(
        queryset=User.objects.none(),  # initially none
        widget=forms.Select(attrs={"class": "browser-default custom-select"}),
        label="Lecturer",
    )

    class Meta:
        model = CourseAllocation
        fields = ["lecturer", "courses"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'is_faculty_admin') and user.is_faculty_admin:
            faculty = user.faculty
            self.fields["lecturer"].queryset = User.objects.filter(is_lecturer=True, faculty=faculty)
            self.fields["courses"].queryset = Course.objects.filter(program__faculty=faculty)


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class CourseAllocationEditView(UpdateView):
    model = CourseAllocation
    form_class = EditCourseAllocationForm
    template_name = 'faculty_admin/course_allocation_form.html'
    success_url = reverse_lazy('faculty_course_allocation_view')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['courses'].queryset = form.fields['courses'].queryset.filter(program__faculty=self.request.user.faculty)
        return form


@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyProgramDeleteView(DeleteView):
    model = Program
    success_url = reverse_lazy('faculty_program_list')

    def dispatch(self, request, *args, **kwargs):
        program = self.get_object()
        if program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        messages.success(request, "Program deleted successfully.")
        return self.post(request, *args, **kwargs)

class CourseAllocationCreateView(CreateView):
    model = CourseAllocation
    form_class = CourseAllocationForm
    template_name = 'faculty_admin/course_allocation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # 👈 ensures faculty filtering works
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Courses successfully allocated.")
        return redirect('faculty_course_allocation_view')

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class CourseAllocationDeleteView(DeleteView):
    model = CourseAllocation
    success_url = reverse_lazy('faculty_course_allocation_view')

    def dispatch(self, request, *args, **kwargs):
        allocation = self.get_object()
        # Ensure the user is only deleting within their faculty
        if allocation.courses.exists():
            first_course = allocation.courses.first()
            if first_course.program.faculty != request.user.faculty:
                return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        messages.success(request, "Course allocation deleted successfully.")
        return self.post(request, *args, **kwargs)

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyCourseDeleteView(DeleteView):
    model = Course
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    template_name = 'faculty_admin/course_confirm_delete.html'  # Optional: create a template or skip
    success_url = reverse_lazy('faculty_course_list')

    def dispatch(self, request, *args, **kwargs):
        course = self.get_object()
        if course.program.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        messages.success(request, "Course deleted successfully.")
        return self.post(request, *args, **kwargs)

# faculty_admin/views.py

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyLecturerAddView(CreateView):
    model = User
    form_class = FacultyLecturerAddForm
    template_name = 'faculty_admin/add_staff.html'
    success_url = reverse_lazy('faculty_lecturer_list')

    def form_valid(self, form):
        # Save lecturer with assigned faculty
        user = form.save(commit=False, faculty=self.request.user.faculty)
        password = get_random_string(8)
        user.set_password(password)
        user.save()

        # Send welcome email using lecturer email template
        subject = "Lecturer Account Created"
        message = render_to_string("accounts/email/new_lecturer_account_confirmation.html", {
            "user": user,
            "password": password,
        })
        email = EmailMessage(subject, message, settings.EMAIL_FROM_ADDRESS, [user.email])
        email.content_subtype = "html"
        email.send(fail_silently=True)

        messages.success(self.request, f"Lecturer {user.get_full_name} created successfully.")
        return redirect(self.success_url)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        return form

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyLecturerEditView(UpdateView):
    model = User
    form_class = FacultyLecturerEditForm
    template_name = 'faculty_admin/edit_lecturer.html'  # ← updated template name
    success_url = reverse_lazy('faculty_lecturer_list')
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.is_lecturer or obj.faculty != request.user.faculty:
            return redirect('permission_denied')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Lecturer updated successfully.")
        return super().form_valid(form)

@method_decorator([login_required, faculty_admin_required], name='dispatch')
class FacultyLecturerListPDFView(View):
    def get(self, request, *args, **kwargs):
        faculty = request.user.faculty
        lecturers = User.objects.filter(is_lecturer=True, faculty=faculty)

        template_path = 'pdf/faculty_lecturer_list.html'
        context = {
            'lecturers': lecturers,
            'faculty': faculty,
            'site_settings': SiteSettings.get_settings(),
        }

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="lecturers_list.pdf"'

        template = get_template(template_path)
        html = template.render(context)

        pisa_status = pisa.CreatePDF(
            html,
            dest=response,
            link_callback=pdf_link_callback,
        )
        if pisa_status.err:
            return HttpResponse('Error generating PDF: %s' % pisa_status.err)
        return response


def form_valid(self, form):
    user = form.save(commit=False)
    user.is_lecturer = True
    user.faculty = self.request.user.faculty
    user.username = f"lec{get_random_string(5)}"
    password = get_random_string(8)
    user.set_password(password)
    user.save()

    log_activity(self.request.user, "Add Lecturer", f"Added lecturer {user.get_full_name}")

    return super().form_valid(form)
