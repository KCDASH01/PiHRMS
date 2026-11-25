"""Record-level authorization for attendance request actions."""

import re

from django.conf import settings

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


def can_access_request_employee(request, employee, permission, *, allow_self=False):
    user = request.user
    actor = getattr(user, "employee_get", None)
    if actor is None or employee is None:
        return False
    if actor.pk == employee.pk:
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
        app_label, codename = permission.split(".", 1)
        if user.user_permissions.filter(
            content_type__app_label=app_label, codename=codename
        ).exists() or user.company_group_assignments.filter(
            company_id=company_id,
            group__permissions__content_type__app_label=app_label,
            group__permissions__codename=codename,
        ).exists():
            return True
    elif user.has_perm(permission):
        return True

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
