from rest_framework import serializers


class FollowUpReference(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    revision = serializers.IntegerField(min_value=0)
