from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import Notification
from api.serializers.notifications import NotificationSerializer


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
        read_param = self.request.query_params.get("read")
        unread_param = self.request.query_params.get("unread")
        if unread_param == "true" or read_param == "false":
            qs = qs.filter(read=False)
        elif read_param == "true":
            qs = qs.filter(read=True)
        return qs

    @action(detail=False, methods=["post"], url_path="mark_all_read")
    def mark_all_read(self, request):
        updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"marked": updated})
