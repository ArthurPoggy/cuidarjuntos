# care/context_processors.py
from .models import GroupMembership

def current_group(request):
    if not request.user.is_authenticated:
        return {"current_group": None, "current_group_membership": None}
    try:
        gm = GroupMembership.objects.select_related("group").get(user=request.user)
        return {"current_group": gm.group, "current_group_membership": gm}
    except GroupMembership.DoesNotExist:
        return {"current_group": None, "current_group_membership": None}
