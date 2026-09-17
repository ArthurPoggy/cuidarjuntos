# care/context_processors.py
def current_group(request):
    if not request.user.is_authenticated:
        return {"current_group": None, "current_group_membership": None}
    # Fallback transitorio (tarefa #38): primeiro grupo do usuario, ja que
    # um usuario agora pode ter varios GroupMembership. Ver
    # `api.views.care._get_patient` para o racional completo.
    gm = (
        request.user.group_memberships
        .select_related("group")
        .order_by("id")
        .first()
    )
    if gm is None:
        return {"current_group": None, "current_group_membership": None}
    return {"current_group": gm.group, "current_group_membership": gm}
