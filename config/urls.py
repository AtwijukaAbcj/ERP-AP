from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views import defaults as default_views
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import JavaScriptCatalog
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from result.urls import urlpatterns as result_urlpatterns
from quiz.views import QuizMarkingList, QuizUserProgressView, quiz_list

admin.site.site_header = "FalconLMS Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
]

urlpatterns += i18n_patterns(
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("messages/", include("messaging.urls")),
    path("course/", include("course.urls")),
    path("assignment/", include("assignment.urls")),
    path("finance/", include("finance.urls", namespace="finance")),
    path("procurement/", include("procurement.urls", namespace="procurement")),
    path("audit/", include("audit.urls")),
    path("admissions/", include("admissions.urls")),
    path("clinical/", include("clinical.urls")),
    path("results/", include((result_urlpatterns, None))),
    path("quizzes/progress/", QuizUserProgressView.as_view(), name="quiz_progress"),
    path("quizzes/marking_list/", QuizMarkingList.as_view(), name="quiz_marking"),
    path("courses/<slug:slug>/quizzes/", quiz_list, name="quiz_index"),
    path("search/", include("search.urls")),
    path("voting/", include("voting.urls")),
    path('api/', include('config.api_urls')),
)


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
