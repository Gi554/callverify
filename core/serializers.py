from rest_framework import serializers
from .models import Campaign, Prospect, ImportBatch, LookupCheck, ExportJob, AuditEvent, Suppression, ConsentEvidence, CallCampaign

class CampaignSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()
    def get_progress(self,obj):
        total=obj.prospects.filter(phone__isnull=False).count()
        checked=LookupCheck.objects.filter(campaign=obj,status='completed').values('phone').distinct().count()
        return {'total':total,'checked':checked,'errors':LookupCheck.objects.filter(campaign=obj,status='error').count(),
            'pending':LookupCheck.objects.filter(campaign=obj,status__in=['pending','running']).count(),
            'percent':min(100,round(100*checked/total)) if total else 0}
    class Meta:
        model = Campaign
        fields = '__all__'
        read_only_fields = ['owner','spent','status','created_at']
    def validate_budget(self, value):
        if value < 0 or (self.instance and value < self.instance.spent):
            raise serializers.ValidationError('Budget inférieur à zéro ou aux dépenses réservées')
        return value

class ProspectSerializer(serializers.ModelSerializer):
    technical_results = serializers.SerializerMethodField()
    def get_technical_results(self, obj):
        from .qualification import technical_results
        return technical_results(obj)
    e164 = serializers.CharField(source='phone.e164', read_only=True, default=None)
    line_status = serializers.CharField(source='phone.line_status', read_only=True, default='unknown')
    carrier = serializers.CharField(source='phone.carrier', read_only=True, default='')
    line_type = serializers.CharField(source='phone.line_type', read_only=True, default='')
    class Meta:
        model = Prospect
        exclude = ['c2']

class ImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportBatch
        exclude = ['original']
        read_only_fields = ['status','report']

class LookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupCheck
        fields = '__all__'

class ExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportJob
        exclude = ['file']

class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = '__all__'

class SuppressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Suppression
        fields = '__all__'
    def validate_e164(self, value):
        from .services import normalize
        normalized, _, _ = normalize(value)
        if not normalized:
            raise serializers.ValidationError('Numéro canadien invalide')
        return normalized

class ConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentEvidence
        fields = '__all__'
        read_only_fields = ['recorded_by','created_at']
    def validate_expires_at(self, value):
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError('La preuve doit être encore valide')
        return value

class CallCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallCampaign
        fields = '__all__'
        read_only_fields = ['status','compliance_approved']
