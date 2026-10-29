from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def has_permission(context, permission_code):
    request = context.get('request')
    if not request or not hasattr(request, 'user'):
        return False
    return request.user.has_permission(permission_code)


@register.simple_tag(takes_context=True)
def can_access_module(context, module_name):
    request = context.get('request')
    if not request or not hasattr(request, 'user'):
        return False
    return request.user.can_access_module(module_name)


@register.simple_tag(takes_context=True)
def has_module_permission(context, permission_code):
    """Legacy alias for permission checks.

    This keeps old templates compatible while using the action-level
    permission system under the hood.
    """
    request = context.get('request')
    if not request or not hasattr(request, 'user'):
        return False
    return request.user.has_permission(permission_code)
