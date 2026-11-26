"""Record-level authorization for attendance request actions."""

import re

from django.conf import settings
from django.db.models import Q

from base.auth_backends import company_scoped_active, get_allowed_company_ids


def find_request_employee(employee_id):
    """Look up the submitted BigAutoField key through the company-aware manager."""
    from employee.models import Employee

    value = str(employee_id)
    if re.fullmatch(r"[0-9]{1,19}", value) is None:
        return None
    employee_pk = int(value)
    if not 0 < employee_pk <= 2**63 - 1:
        return None
    return Employee.objects.filter(pk=employee_pk).first()


def _permission_grants(user, permission):
    app_label, codename = permission.split(".", 1)
    direct = user.user_permissions.filter(
        content_type__app_label=app_label, codename=codename
    ).exists()
    assignments = user.company_group_assignments.filter(
        group__permissions__content_type__app_label=app_label,
        group__permissions__codename=codename,
    )
    return direct, assignments


def can_access_request_employee(
    request, employee, permission, *, allow_self=False, allow_self_with_permission=False
):
    user = request.user
    actor = getattr(user, "employee_get", None)
    if actor is None or employee is None:
        return False
    is_self = actor.pk == employee.pk
    if is_self and (allow_self or not allow_self_with_permission):
        return allow_self
    if user.is_superuser:
        return True

    work_info = getattr(employee, "employee_work_info", None)
    if company_scoped_active():
        company_id = getattr(work_info, "company_id_id", None)
        if company_id is None or company_id not in get_allowed_company_ids(user):
            return False
        # "All my companies" can grant the union of group permissions. A
        # mutation must use the grant for the employee's actual company.
        direct, assignments = _permission_grants(user, permission)
        if direct or assignments.filter(company_id=company_id).exists():
            return True
    elif user.has_perm(permission):
        return True

    if is_self:
        return False
    seen = {employee.pk}
    manager = getattr(work_info, "reporting_manager_id", None)
    while manager is not None and manager.pk not in seen:
        if manager.pk == actor.pk:
            return True
        if not settings.NESTED_SUBORDINATE_VISIBILITY:
            break
        seen.add(manager.pk)
        manager_work_info = getattr(manager, "employee_work_info", None)
        manager = getattr(manager_work_info, "reporting_manager_id", None)
    return False


def can_write_attendance_employees(request, employee_ids, permission):
    """Check every submitted ID before binding a potentially multi-employee form."""
    return all(
        can_access_request_employee(
            request, find_request_employee(employee_id), permission,
            allow_self_with_permission=True,
        )
        for employee_id in dict.fromkeys(employee_ids)
    )


def can_approve_daily_attendance(request, employee):
    """Scope validation and overtime approval, preserving superuser self-approval."""
    return can_access_request_employee(
        request, employee, "attendance.change_attendance",
        allow_self=request.user.is_superuser,
    )


def attendance_employee_read_scope(request, permission):
    """Return employees visible to self, their managers and scoped permission holders."""
    from employee.models import Employee

    user = request.user
    employees = Employee.objects.all()
    if user.is_superuser:
        return employees
    actor = getattr(user, "employee_get", None)
    if actor is None:
        return employees.none()

    eligible = employees
    scope = Q(pk=actor.pk)
    if company_scoped_active():
        eligible = eligible.filter(employee_work_info__company_id__in=get_allowed_company_ids(user))
        direct, assignments = _permission_grants(user, permission)
        if direct:
            return employees.filter(scope | Q(pk__in=eligible.values("pk")))
        scope |= Q(employee_work_info__company_id__in=assignments.values("company_id"))
    elif user.has_perm(permission):
        return employees

    seen = {actor.pk}
    frontier = seen
    reports = set()
    while frontier:
        frontier = set(eligible.filter(
            employee_work_info__reporting_manager_id__in=frontier
        ).values_list("pk", flat=True)) - seen
        reports.update(frontier)
        seen.update(frontier)
        if not settings.NESTED_SUBORDINATE_VISIBILITY:
            break
    return employees.filter(scope | Q(pk__in=reports))
