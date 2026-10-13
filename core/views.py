import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.http import FileResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from twilio.request_validator import RequestValidator
from .models import *
from .serializers import *
from .permissions import AdminOnly, SuperAdminOnly
from .services import read_table, schedule_lookup, filtered_prospects, EXPORT_COLUMNS, FILTERS
from .tasks import import_task, export_task
from .security import decrypt_secret, consume_backup, generate_backup_codes
from .delivery import enqueue

def audit(user, action_name, obj=None, metadata=None):
    AuditEvent.objects.create(actor=user if user.is_authenticated else None, action=action_name,
        object_id=str(obj.pk) if obj else '', metadata=metadata or {})

def owned_campaign(user, pk):
    queryset = Campaign.objects.all() if user.is_superuser else Campaign.objects.filter(owner=user)
    from django.shortcuts import get_object_or_404
    try:pk=int(pk)
    except (ValueError,TypeError):raise ValidationError('Identifiant de campagne invalide')
    return get_object_or_404(queryset, pk=pk)

def totp_step(secret, code):
    if not secret or not isinstance(code, str) or len(code) != 6 or not code.isdigit():
        return None
    try:
        key = base64.b32decode(decrypt_secret(secret))
    except Exception:
        return None
    counter = int(time.time()) // 30
    for offset in (-1, 0, 1):
        digest = hmac.new(key, struct.pack('>Q', counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 15
        value = (struct.unpack('>I', digest[index:index+4])[0] & 0x7fffffff) % 1000000
        if hmac.compare_digest(f'{value:06}', code):
            return counter + offset
    return None

def valid_totp(secret, code):
    return totp_step(secret, code) is not None

class LoginThrottle(AnonRateThrottle):
    scope = 'login'

@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'csrfToken':get_token(request)})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
@csrf_protect
def login_view(request):
    user = authenticate(request, username=request.data.get('username'), password=request.data.get('password'))
    if not user or not user.is_staff or not user.is_active:
        audit(request.user, 'login.failed')
        return Response({'detail':'Identifiants invalides'}, status=401)
    if user.is_superuser or user.mfa_enabled:
        with transaction.atomic():
            user = AdminUser.objects.select_for_update().get(pk=user.pk)
            step = totp_step(user.mfa_secret, request.data.get('code'))
            backup = consume_backup(user,request.data.get('code')) if step is None else False
            if not backup and (step is None or step <= user.last_mfa_step):
                return Response({'detail':'Code MFA requis, invalide ou déjà utilisé'}, status=401)
            if not backup:
                user.last_mfa_step = step
                user.save(update_fields=['last_mfa_step'])
    login(request, user)
    audit(user, 'login.success')
    return Response({'id':user.pk, 'username':user.username, 'superadmin':user.is_superuser})

@api_view(['GET','POST'])
def session_view(request):
    if request.method == 'POST':
        audit(request.user, 'logout')
        logout(request)
        return Response(status=204)
    return Response({'id':request.user.pk,'username':request.user.username,'superadmin':request.user.is_superuser,'mfa_enabled':request.user.mfa_enabled,'backup_remaining':len(request.user.backup_codes)})

class OwnedViewSet(viewsets.GenericViewSet):
    def restrict(self, queryset, path='campaign__owner'):
        return queryset if self.request.user.is_superuser else queryset.filter(**{path:self.request.user})

class CampaignViewSet(OwnedViewSet, viewsets.ModelViewSet):
    serializer_class = CampaignSerializer
    def get_queryset(self):
        queryset=self.restrict(Campaign.objects.order_by('-created_at'), 'owner')
        if self.request.query_params.get('search'):
            queryset=queryset.filter(name__icontains=self.request.query_params['search'])
        if self.request.query_params.get('status'):
            queryset=queryset.filter(status=self.request.query_params['status'])
        return queryset
    def perform_create(self, serializer):
        obj = serializer.save(owner=self.request.user)
        audit(self.request.user, 'campaign.created', obj)
    def perform_update(self, serializer):
        obj = serializer.save()
        audit(self.request.user, 'campaign.updated', obj)
    def update(self,request,*args,**kwargs):
        with transaction.atomic():
            obj=Campaign.objects.select_for_update().get(pk=self.get_object().pk)
            serializer=self.get_serializer(obj,data=request.data,partial=kwargs.pop('partial',False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        return Response(serializer.data)
    def destroy(self, request, *args, **kwargs):
        raise ValidationError('Utiliser archive pour conserver la traçabilité')
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'archived'
        campaign.save(update_fields=['status'])
        audit(request.user, 'campaign.archived', campaign)
        return Response(self.get_serializer(campaign).data)
    @action(detail=True, methods=['post'])
    def lookup(self, request, pk=None):
        force = request.data.get('force', False)
        if not isinstance(force, bool):
            raise ValidationError('force doit être un booléen')
        try:
            result = schedule_lookup(self.get_object(), force)
        except ValueError as error:
            raise ValidationError(str(error))
        audit(request.user, 'lookup.scheduled', self.get_object(), result)
        return Response(result, status=202)

class ImportViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    search_fields=['campaign__name','original']
    serializer_class = ImportSerializer
    def get_queryset(self):
        qs=self.restrict(ImportBatch.objects.order_by('-created_at'))
        if self.request.query_params.get('campaign'):
            qs=qs.filter(campaign_id=self.request.query_params['campaign'])
        return qs
    @action(detail=True,methods=['post'])
    def preview(self,request,pk=None):
        batch=self.get_object()
        if batch.status!='preview':
            raise ValidationError('Import déjà confirmé')
        batch.sheet=request.data.get('sheet','')
        try:
            headers,rows,sheets=read_table(batch)
        except (ValueError,KeyError):
            raise ValidationError('Feuille inconnue ou fichier indisponible')
        batch.save(update_fields=['sheet'])
        return Response({'id':batch.pk,'headers':headers,'preview':rows[:10],'rows':len(rows),'sheets':sheets,'sheet':batch.sheet})
    @action(detail=True,methods=['get'])
    def report(self,request,pk=None):
        import csv,io
        from django.http import HttpResponse
        from .services import safe_cell
        batch=self.get_object()
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(['ligne','doublon','erreur','contact'])
        for row in batch.rows.filter(Q(duplicate=True)|~Q(error='')).iterator():
            writer.writerow([row.line,row.duplicate,safe_cell(row.error),row.prospect_id or ''])
        audit(request.user,'import.report_downloaded',batch)
        response=HttpResponse(output.getvalue().encode('utf-8-sig'),content_type='text/csv')
        response['Content-Disposition']=f'attachment; filename="import-{batch.pk}-rapport.csv"'
        return response
    @action(detail=True,methods=['post'])
    def retry(self,request,pk=None):
        with transaction.atomic():
            batch=ImportBatch.objects.select_for_update().get(pk=self.get_object().pk)
            if batch.status!='error' or not batch.original:
                raise ValidationError('Aucun import en erreur disponible')
            batch.status='queued';batch.save(update_fields=['status'])
            TaskDelivery.objects.filter(kind='import',object_id=batch.pk).update(status='pending',available_at=timezone.now())
            enqueue('import',batch.pk)
        audit(request.user,'import.retried',batch)
        return Response({'status':'queued'},status=202)
    def create(self, request):
        campaign = owned_campaign(request.user, request.data.get('campaign'))
        if campaign.status == 'archived':
            raise ValidationError('Campagne archivée')
        upload = request.FILES.get('file')
        if not upload or not upload.name.lower().endswith(('.csv','.xlsx')) or upload.size > settings.MAX_IMPORT_BYTES:
            raise ValidationError('Fichier CSV/XLSX requis, maximum 20 Mo')
        batch = ImportBatch.objects.create(campaign=campaign, original=upload, sheet=request.data.get('sheet',''))
        try:
            headers, rows, sheets = read_table(batch)
        except Exception:
            batch.original.delete()
            batch.delete()
            raise ValidationError('Fichier vide, corrompu ou structure invalide')
        audit(request.user, 'import.uploaded', batch)
        return Response({'id':batch.pk,'headers':headers,'preview':rows[:10],'rows':len(rows),'sheets':sheets}, status=201)
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            batch = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if batch.status != 'preview':
                raise ValidationError('Import déjà confirmé')
            mapping = request.data.get('mapping',{})
            headers, _, _ = read_table(batch)
            if not isinstance(mapping,dict) or set(mapping)-{'phone','name','reference'} or mapping.get('phone') not in headers or any(v not in headers for v in mapping.values()):
                raise ValidationError('Mappage invalide; phone obligatoire')
            batch.mapping = mapping
            batch.status = 'queued'
            batch.save(update_fields=['mapping','status'])
            enqueue('import',batch.pk)
        audit(request.user, 'import.confirmed', batch)
        return Response({'id':batch.pk,'status':'queued'},status=202)

class ProspectViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    serializer_class = ProspectSerializer
    def get_queryset(self):
        queryset = self.restrict(Prospect.objects.select_related('phone').order_by('pk'))
        for field in ['campaign','validity','compliance','phone__line_status']:
            if self.request.query_params.get(field):
                queryset = queryset.filter(**{field:self.request.query_params[field]})
        if self.request.query_params.get('search'):
            from django.db.models import Q
            term=self.request.query_params['search']
            queryset = queryset.filter(Q(raw_phone__icontains=term)|Q(phone__e164__icontains=term)|Q(name__icontains=term)|Q(reference__icontains=term))
        return queryset
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        prospect = self.get_object()
        checks = LookupCheck.objects.filter(phone=prospect.phone, campaign=prospect.campaign).order_by('-created_at') if prospect.phone else []
        audit(request.user, 'prospect.history', prospect)
        return Response({'lookup':LookupSerializer(checks,many=True).data,
            'consents':ConsentSerializer(prospect.consents.all(),many=True).data,
            'sources':list(prospect.importrow_set.values('batch_id','line','duplicate','error')),
            'suppressed':bool(prospect.phone and Suppression.objects.filter(e164=prospect.phone.e164).exists())})
    @action(detail=True,methods=['post'])
    def classify(self,request,pk=None):
        prospect=self.get_object()
        value=request.data.get('compliance')
        reason=request.data.get('reason','')
        if value not in ('allowed','forbidden','review') or not isinstance(reason,str) or len(reason.strip())<10:
            raise ValidationError('Statut et justification détaillée obligatoires')
        if value=='allowed' and (not prospect.phone or Suppression.objects.filter(e164=prospect.phone.e164).exists()
            or not prospect.consents.filter(expires_at__gt=timezone.now()).exists()):
            raise ValidationError('Numéro exclu ou preuve valide manquante')
        prospect.compliance=value;prospect.compliance_reason=reason
        prospect.save(update_fields=['compliance','compliance_reason'])
        audit(request.user,'prospect.compliance_changed',prospect,{'status':value,'reason':reason})
        return Response(self.get_serializer(prospect).data)

class LookupViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    serializer_class = LookupSerializer
    def get_queryset(self):
        return self.restrict(LookupCheck.objects.order_by('-created_at'))
    @action(detail=True,methods=['post'],permission_classes=[SuperAdminOnly])
    def reconcile(self,request,pk=None):
        from decimal import Decimal,InvalidOperation
        check=self.get_object()
        reference=request.data.get('invoice_reference','')
        try:
            amount=Decimal(str(request.data.get('actual_cost')))
            if not amount.is_finite() or amount<0 or amount>Decimal('99999999'):
                raise ValueError
        except (InvalidOperation,ValueError):
            raise ValidationError('Coût facturé invalide')
        if not isinstance(reference,str) or not reference.strip():
            raise ValidationError('Référence de facture requise')
        check.actual_cost=amount;check.save(update_fields=['actual_cost'])
        audit(request.user,'lookup.cost_reconciled',check,{'actual_cost':str(amount),'invoice_reference':reference[:250]})
        return Response(self.get_serializer(check).data)

class ExportViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    search_fields=['campaign__name','format']
    serializer_class = ExportSerializer
    def get_queryset(self):
        qs=self.restrict(ExportJob.objects.order_by('-pk'))
        if self.request.query_params.get('campaign'):
            qs=qs.filter(campaign_id=self.request.query_params['campaign'])
        return qs
    def create(self, request):
        campaign = owned_campaign(request.user, request.data.get('campaign'))
        format_name = request.data.get('format','csv')
        columns = request.data.get('columns',EXPORT_COLUMNS)
        filters = request.data.get('filters',{})
        if format_name not in ('csv','xlsx') or not isinstance(columns,list) or not columns or any(not isinstance(c,str) for c in columns) or set(columns)-set(EXPORT_COLUMNS):
            raise ValidationError('Format ou colonnes invalides')
        if not isinstance(filters,dict) or set(filters)-FILTERS or any(not isinstance(v,str) for v in filters.values()):
            raise ValidationError('Filtres invalides')
        config,_=PlatformSettings.objects.get_or_create(pk=1)
        with transaction.atomic():
            job = ExportJob.objects.create(campaign=campaign, author=request.user, format=format_name,
                columns=columns, filters=filters, expires_at=timezone.now()+timedelta(hours=config.export_hours))
            enqueue('export',job.pk)
        audit(request.user, 'export.requested', job)
        return Response(self.get_serializer(job).data,status=202)
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        job = self.get_object()
        if job.status != 'completed' or job.expires_at <= timezone.now():
            raise ValidationError('Export non disponible ou expiré')
        audit(request.user, 'export.downloaded', job)
        return FileResponse(job.file.open('rb'), as_attachment=True, filename=f'callverify-{job.pk}.{job.format}')

class ConsentViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConsentSerializer
    def get_queryset(self):
        return self.restrict(ConsentEvidence.objects.order_by('-pk'), 'prospect__campaign__owner')
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prospect = serializer.validated_data['prospect']
        owned_campaign(request.user, prospect.campaign_id)
        evidence = serializer.save(recorded_by=request.user)
        audit(request.user, 'consent.recorded', evidence)
        return Response(serializer.data,status=201)

class SuppressionViewSet(viewsets.ModelViewSet):
    search_fields=['e164','reason']
    queryset = Suppression.objects.order_by('-pk')
    serializer_class = SuppressionSerializer
    permission_classes = [SuperAdminOnly]
    def perform_create(self, serializer):
        audit(self.request.user, 'suppression.created', serializer.save())
    def perform_update(self, serializer):
        audit(self.request.user, 'suppression.updated', serializer.save())
    def perform_destroy(self, instance):
        audit(self.request.user, 'suppression.deleted', instance)
        instance.delete()

class CallCampaignViewSet(OwnedViewSet, viewsets.ReadOnlyModelViewSet):
    search_fields=['campaign__name']
    serializer_class = CallCampaignSerializer
    def get_queryset(self):
        return self.restrict(CallCampaign.objects.order_by('-pk'))
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        owned_campaign(request.user, serializer.validated_data['campaign'].pk)
        obj = serializer.save()
        audit(request.user, 'voice.prepared', obj)
        return Response(serializer.data,status=201)
    @action(detail=True,methods=['get'])
    def eligibility(self,request,pk=None):
        obj=self.get_object()
        decisions=[]
        for prospect in obj.campaign.prospects.select_related('phone'):
            reasons=[]
            if not prospect.phone or prospect.validity!='valid': reasons.append('Numéro techniquement invalide')
            if prospect.compliance!='allowed': reasons.append('Autorisation administrative manquante')
            if not prospect.consents.filter(expires_at__gt=timezone.now()).exists(): reasons.append('Preuve valide manquante')
            if prospect.phone and Suppression.objects.filter(e164=prospect.phone.e164).exists(): reasons.append('Numéro exclu')
            decisions.append({'prospect':prospect.pk,'e164':prospect.phone.e164 if prospect.phone else '',
                'eligible':not reasons,'reasons':reasons})
        return Response({'eligible':sum(d['eligible'] for d in decisions),'total':len(decisions),
            'decisions':decisions,'voice_enabled':False})
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        self.get_object()
        return Response({'detail':'Appels réels désactivés : configuration fournisseur et recette de conformité requises'},status=409)
    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        obj = self.get_object()
        obj.status = 'stopped'
        obj.save(update_fields=['status'])
        audit(request.user, 'voice.stopped', obj)
        return Response(self.get_serializer(obj).data)

class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.order_by('-created_at')
    serializer_class = AuditSerializer
    permission_classes = [SuperAdminOnly]
    def get_queryset(self):
        qs=AuditEvent.objects.order_by('-created_at')
        if self.request.query_params.get('search'):
            qs=qs.filter(action__icontains=self.request.query_params['search'])
        return qs

@api_view(['GET'])
def dashboard(request):
    campaigns = Campaign.objects.all() if request.user.is_superuser else Campaign.objects.filter(owner=request.user)
    prospects = Prospect.objects.filter(campaign__in=campaigns)
    checks = LookupCheck.objects.filter(campaign__in=campaigns)
    validity={row['validity']:row['count'] for row in PhoneNumber.objects.filter(prospect__campaign__in=campaigns)
        .values('validity').annotate(count=Count('id',distinct=True))}
    for row in prospects.filter(phone__isnull=True).values('validity').annotate(count=Count('id')):
        validity[row['validity']]=validity.get(row['validity'],0)+row['count']
    return Response({'campaigns':campaigns.count(), 'imports':ImportBatch.objects.filter(campaign__in=campaigns).count(),
        'unique_numbers':prospects.filter(phone__isnull=False).values('phone').distinct().count(),
        'validity':[{'validity':key,'count':value} for key,value in validity.items()],
        'lookup':list(checks.values('status').annotate(count=Count('phone',distinct=True))),
        'reserved_cost':campaigns.aggregate(total=Sum('spent'))['total'] or 0})

@api_view(['GET','POST','PATCH'])
@permission_classes([SuperAdminOnly])
def administrators(request):
    if request.method == 'GET':
        return Response(list(AdminUser.objects.filter(is_staff=True).values('id','username','email','is_active','is_superuser','mfa_enabled')))
    if request.method == 'PATCH':
        from django.shortcuts import get_object_or_404
        user = get_object_or_404(AdminUser,is_staff=True,pk=request.data.get('id'))
        active = request.data.get('is_active')
        role=request.data.get('role')
        if user.pk == request.user.pk or (active is None and role is None):
            raise ValidationError('Modification de son propre rôle/état interdite ou demande vide')
        fields=[]
        if active is not None:
            if not isinstance(active,bool):raise ValidationError('État invalide')
            user.is_active=active;fields.append('is_active')
        if role is not None:
            if role not in ('administrator','superadministrator'):raise ValidationError('Rôle invalide')
            if role=='superadministrator' and not user.mfa_enabled:
                raise ValidationError('Le compte doit activer son MFA avant la promotion')
            user.is_superuser=role=='superadministrator';fields.append('is_superuser')
        user.save(update_fields=fields)
        audit(request.user, 'admin.state_changed', user,{'is_active':user.is_active,'is_superuser':user.is_superuser})
        return Response({'id':user.pk,'is_active':user.is_active,'is_superuser':user.is_superuser})
    password = request.data.get('password','')
    username = request.data.get('username','')
    if not isinstance(username,str) or not username or len(username)>150 or AdminUser.objects.filter(username=username).exists():
        raise ValidationError('Nom utilisateur invalide ou déjà utilisé')
    invite = request.data.get('invite',False)
    if not isinstance(invite,bool):
        raise ValidationError('invite doit être un booléen')
    if not invite:
        try:
            validate_password(password)
        except DjangoValidationError as error:
            raise ValidationError(error.messages)
    user = AdminUser.objects.create_user(username=username, password=password,
        email=request.data.get('email',''),is_staff=True)
    invitation = None
    if invite:
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        user.set_unusable_password()
        user.save(update_fields=['password'])
        invitation = {'uid':urlsafe_base64_encode(force_bytes(user.pk)),
            'token':default_token_generator.make_token(user)}
    audit(request.user, 'admin.created', user)
    return Response({'id':user.pk,'username':user.username,'invitation':invitation},status=201)

@api_view(['POST'])
def mfa(request):
    if request.data.get('action') == 'backup':
        with transaction.atomic():
            user=AdminUser.objects.select_for_update().get(pk=request.user.pk)
            step=totp_step(user.mfa_secret,request.data.get('code'))
            if not user.check_password(request.data.get('password','')) or step is None or step<=user.last_mfa_step:
                raise ValidationError('Mot de passe et nouveau code MFA requis')
            user.last_mfa_step=step;user.save(update_fields=['last_mfa_step'])
            codes=generate_backup_codes(user)
        audit(user,'mfa.backup_regenerated')
        return Response({'backup_codes':codes})
    if request.data.get('action') == 'enroll':
        if request.user.mfa_enabled:
            raise ValidationError('MFA déjà actif')
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        request.session['pending_mfa'] = secret
        import io
        import qrcode
        import qrcode.image.svg
        from urllib.parse import quote
        uri=f'otpauth://totp/CallVerify:{quote(request.user.username)}?secret={secret}&issuer=CallVerify'
        output=io.BytesIO()
        qrcode.make(uri,image_factory=qrcode.image.svg.SvgPathImage).save(output)
        return Response({'secret':secret,'uri':uri,'qr':'data:image/svg+xml;base64,'+base64.b64encode(output.getvalue()).decode()})
    secret = request.session.get('pending_mfa')
    if not valid_totp(secret, request.data.get('code')):
        raise ValidationError('Code invalide')
    request.user.mfa_secret = secret
    request.user.mfa_enabled = True
    request.user.save(update_fields=['mfa_secret','mfa_enabled'])
    request.session.pop('pending_mfa',None)
    audit(request.user, 'mfa.enabled')
    return Response({'enabled':True,'backup_codes':generate_backup_codes(request.user)})

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def voice_webhook(request):
    if not settings.TWILIO_AUTH_TOKEN:
        return Response(status=503)
    payload = request.POST.dict()
    if not RequestValidator(settings.TWILIO_AUTH_TOKEN).validate(request.build_absolute_uri(), request.POST,
            request.headers.get('X-Twilio-Signature','')):
        return Response(status=403)
    sid = payload.get('CallSid','')
    event_status = payload.get('CallStatus','')
    allowed = {'queued','initiated','ringing','in-progress','completed','busy','no-answer','failed','canceled'}
    if event_status not in allowed:
        return Response(status=400)
    fingerprint = hashlib.sha256(f"{sid}:{event_status}:{payload.get('SequenceNumber','')}".encode()).hexdigest()
    with transaction.atomic():
        attempt = CallAttempt.objects.select_for_update().filter(sid=sid).first()
        if not attempt:
            return Response(status=404)
        _, created = WebhookEvent.objects.get_or_create(fingerprint=fingerprint, defaults={'payload':payload})
        if created:
            terminal = {'completed','busy','no-answer','failed','canceled'}
            ranks = {'queued':0,'initiated':1,'ringing':2,'in-progress':3}
            if attempt.status not in terminal and (event_status in terminal or ranks.get(event_status,0)>=ranks.get(attempt.status,0)):
                attempt.status = event_status
                if payload.get('CallDuration','').isdigit():
                    attempt.duration = int(payload['CallDuration'])
                attempt.save(update_fields=['status','duration'])
    return Response(status=204)
