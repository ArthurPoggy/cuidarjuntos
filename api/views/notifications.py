from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import Notification
from api.serializers.notifications import NotificationSerializer

_TRUE_VALUES = {"true", "1", "yes"}
_FALSE_VALUES = {"false", "0", "no"}


def _parse_bool(value):
    """Converte um query param em bool, tolerante a maiúsculas/minúsculas e 1/0.

    Retorna None quando o valor está ausente ou não é reconhecido.
    """
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.action != "list":
            return qs

        read_param = _parse_bool(self.request.query_params.get("read"))
        unread_param = _parse_bool(self.request.query_params.get("unread"))
        if unread_param is True or read_param is False:
            qs = qs.filter(read=False)
        elif read_param is True:
            qs = qs.filter(read=True)
        return qs

    @action(detail=False, methods=["post"], url_path="mark_all_read")
    def mark_all_read(self, request):
        updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"marked": updated})
