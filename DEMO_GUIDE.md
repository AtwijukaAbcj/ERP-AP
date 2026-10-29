# FalconLMS - System Demo Guide

## Overview
FalconLMS is a comprehensive Learning Management System designed for educational institutions to manage students, lecturers, courses, results, and more.

---

## 1. Login Page
**URL:** `/accounts/login/`

The modern login page features:
- Clean, responsive design
- Custom school branding (logo upload)
- Language selection
- 2FA verification support

![Login Page](screenshots/01_login.png)

---

## 2. Dashboard (Admin View)
**URL:** `/dashboard/`

The admin dashboard provides:
- Quick statistics (students, lecturers, programs)
- Recent activity overview
- System health indicators

![Dashboard](screenshots/02_dashboard.png)

---

## 3. Sidebar Navigation
The sidebar includes:
- Role-based menu items
- Clickable logo for settings (admin)
- Organized sections: Administration, People, Finance, etc.

![Sidebar](screenshots/03_sidebar.png)

---

## 4. Site Settings
**URL:** `/settings/`

Admins can customize:
- School name and branding
- Logo upload (light and dark versions)
- Contact information
- Primary color theme

![Site Settings](screenshots/04_site_settings.png)

---

## 5. Student Management
**URL:** `/accounts/students/`

Features:
- Student list with search and filters
- Clean table design with alternating rows
- Quick actions for each student

![Student List](screenshots/05_students.png)

---

## 6. Lecturer Management
**URL:** `/accounts/lecturers/`

Features:
- Lecturer profiles
- Course assignments
- Performance tracking

![Lecturer List](screenshots/06_lecturers.png)

---

## 7. Programs & Courses
**URL:** `/programs/`

Features:
- Program management
- Course allocation
- Curriculum planning

![Programs](screenshots/07_programs.png)

---

## 8. Course Registration
**URL:** `/programs/course/registration/`

Students can:
- View available courses
- Register for courses
- Drop courses

![Course Registration](screenshots/08_course_registration.png)

---

## 9. Results Management
**URL:** `/result/`

Features:
- Grade entry by lecturers
- Result verification
- Transcript generation

![Results](screenshots/09_results.png)

---

## 10. Finance Module
**URL:** `/finance/`

Features:
- Student fee management
- Payment tracking
- Invoice generation

![Finance](screenshots/10_finance.png)

---

## 11. Timetable Management
**URL:** `/timetables/`

Features:
- Class scheduling
- Room allocation
- Student/lecturer timetable views

![Timetable](screenshots/11_timetable.png)

---

## 12. Quiz Module
**URL:** `/quiz/`

Features:
- Quiz creation
- Automated grading
- Progress tracking

![Quiz](screenshots/12_quiz.png)

---

## 13. User Profile
**URL:** `/accounts/profile/`

Features:
- Profile information display
- Edit profile option
- Password change

![Profile](screenshots/13_profile.png)

---

## Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Super Admin | superadmin | OnRpAdxWZYAE |
| Admin | admin | rXktnvO21vhg |

---

## Key Features Summary

✅ **Modern UI** - Clean, responsive Bootstrap 5 design  
✅ **Role-Based Access** - Different views for Admin, Lecturer, Student  
✅ **Multi-Language** - English, French, Spanish, Russian  
✅ **Custom Branding** - Upload school logo and colors  
✅ **Secure** - 2FA verification, password policies  
✅ **Finance** - Fee management and invoicing  
✅ **Academic** - Programs, courses, results, timetables  
✅ **Assessments** - Quiz module with auto-grading  

---

## Technical Stack

- **Backend:** Django 6.0.3
- **Frontend:** Bootstrap 5.3.2, FontAwesome 6
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Authentication:** Django Auth + 2FA

---

*Document generated for FalconLMS Demo*
