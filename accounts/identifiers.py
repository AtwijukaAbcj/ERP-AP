import calendar
import re
from string import Formatter

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify


REGISTRATION_NUMBER_FORMAT_DEFAULT = (
    "{program_code}-{intake_month_short}-{year_short}-{sequence:06}"
)
REGISTRATION_NUMBER_FORMAT_FIELDS = {
    "program",
    "program_code",
    "intake_month",
    "intake_month_short",
    "year",
    "year_short",
    "sequence",
}


def validate_registration_number_format(value):
    try:
        fields = list(Formatter().parse(value))
    except ValueError as error:
        raise ValidationError("Enter a valid registration number format.") from error

    field_names = set()
    for _, field_name, format_spec, conversion in fields:
        if field_name is None:
            continue
        if field_name not in REGISTRATION_NUMBER_FORMAT_FIELDS or conversion:
            raise ValidationError(
                "Use {program_code}, {intake_month_short}, {year_short}, and "
                "{sequence} fields."
            )
        if field_name != "sequence" and format_spec:
            raise ValidationError(
                "Only {sequence} supports a format specifier, such as {sequence:06}."
            )
        if field_name == "sequence" and format_spec and not re.fullmatch(
            r"0[1-8]d?", format_spec
        ):
            raise ValidationError(
                "Format the sequence with zero padding, for example {sequence:06}."
            )
        field_names.add(field_name)

    if "sequence" not in field_names:
        raise ValidationError("The registration number format must include {sequence}.")
    return value


def _admission_parts(student):
    cohort = student.cohort or ""
    month = None
    for month_number in range(1, 13):
        names = (calendar.month_name[month_number], calendar.month_abbr[month_number])
        if any(
            re.search(rf"\b{re.escape(name)}\b", cohort, re.IGNORECASE)
            for name in names
            if name
        ):
            month = calendar.month_name[month_number]
            break

    admission_date = student.admission_date
    if month is None:
        month = calendar.month_name[
            admission_date.month if admission_date else timezone.localdate().month
        ]

    cohort_year = re.search(r"\b(19|20)\d{2}\b", cohort)
    year = (
        cohort_year.group(0)
        if cohort_year
        else admission_date.year
        if admission_date
        else timezone.localdate().year
    )
    program = slugify(student.program.title) if student.program_id else "general"
    program_code = student.program.code if student.program_id else "GEN"
    legacy_program = (
        slugify(student.program.title) if student.program_id else "general"
    )
    return program_code, legacy_program, month, year


def generate_student_registration_number(student):
    from core.models import SiteSettings

    settings = SiteSettings.get_settings()
    pattern = validate_registration_number_format(
        settings.student_registration_number_format
    )
    program_code, legacy_program, intake_month, year = _admission_parts(student)
    sequence = student.pk

    while True:
        candidate = pattern.format(
            program_code=program_code,
            program=legacy_program,
            intake_month=intake_month,
            intake_month_short=intake_month[:3],
            year=year,
            year_short=str(year)[-2:],
            sequence=sequence,
        )
        if len(candidate) > 60:
            raise ValidationError(
                "The generated registration number exceeds the 60-character limit."
            )
        existing = type(student).objects.filter(
            registration_number=candidate
        ).exclude(pk=student.pk)
        if not existing.exists():
            return candidate
        sequence += 1
