"""Delegated access administration, strictly confined to the actor's workspace."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction,IntegrityError
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Membership,AccessAudit,ROLES
from .client_policy import available as client_available,immutable as client_immutable

def require_admin(user,workspace):
    if workspace not in ROLES or not Membership.objects.filter(user=user,workspace=workspace,role='administrator',active=True).exists():
        raise PermissionDenied('Administration non autorisée dans cet espace')

def lock_admin(user,workspace):
    # A consistent order serializes concurrent changes to this workspace's grants.
    rows=list(Membership.objects.select_for_update().filter(workspace=workspace).order_by('pk'))
    if not any(row.user_id==user.pk and row.active and row.role=='administrator' for row in rows):
        raise PermissionDenied('Administration non autorisée dans cet espace')
    return rows

class MembershipOutput(serializers.ModelSerializer):
    username=serializers.CharField(source='user.username',read_only=True)
    email=serializers.EmailField(source='user.email',read_only=True)
    account_active=serializers.BooleanField(source='user.is_active',read_only=True)
    class Meta:
        model=Membership
        fields=['id','username','email','role','active','account_active']

class AccessInput(serializers.Serializer):
    username=serializers.CharField(max_length=150)
    email=serializers.EmailField(required=False,allow_blank=True)
    password=serializers.CharField(required=False,write_only=True,trim_whitespace=False,max_length=256)
    role=serializers.CharField()
    existing=serializers.BooleanField(default=False)
    def validate_username(self,value):
        for validator in get_user_model()._meta.get_field('username').validators:
            try:validator(value)
            except DjangoValidationError:raise serializers.ValidationError('Identifiant invalide')
        return value
    def validate_role(self,value):
        if value not in ROLES[self.context['workspace']]:
            raise serializers.ValidationError('Rôle incompatible avec cet espace')
        return value
    def validate(self,data):
        if data['existing']:
            if data.get('password') or data.get('email'):
                raise serializers.ValidationError('Aucun changement du compte existant n’est autorisé ici')
        else:
            if not data.get('password'):
                raise serializers.ValidationError({'password':'Mot de passe initial requis'})
            candidate=get_user_model()(username=data['username'],email=data.get('email',''))
            try:validate_password(data['password'],candidate)
            except DjangoValidationError as error:raise serializers.ValidationError({'password':error.messages})
        return data

class GrantUpdate(serializers.Serializer):
    role=serializers.CharField(required=False)
    active=serializers.BooleanField(required=False)
    def validate(self,data):
        if not data:raise serializers.ValidationError('Aucune modification fournie')
        if 'role' in data and data['role'] not in ROLES[self.context['workspace']]:
            raise serializers.ValidationError({'role':'Rôle incompatible avec cet espace'})
        return data

class AccessPagination(PageNumberPagination):
    page_size=25

@api_view(['GET','POST'])
def users(request,workspace):
    require_admin(request.user,workspace)
    if request.method=='GET':
        qs=Membership.objects.filter(workspace=workspace).select_related('user').order_by('user__username','pk')
        term=request.query_params.get('search','').strip()[:150]
        if term:qs=qs.filter(Q(user__username__icontains=term)|Q(user__email__icontains=term))
        pager=AccessPagination();page=pager.paginate_queryset(qs,request)
        return pager.get_paginated_response(MembershipOutput(page,many=True).data)
    serializer=AccessInput(data=request.data,context={'workspace':workspace})
    serializer.is_valid(raise_exception=True)
    values=serializer.validated_data
    try:
        with transaction.atomic():
            lock_admin(request.user,workspace)
            client_available(workspace,values['role'])
            if values['existing']:
                user=get_user_model().objects.filter(username=values['username'],is_active=True).first()
                if not user:raise ValidationError('Compte indisponible ou déjà associé à cet espace')
            else:
                if get_user_model().objects.filter(username=values['username']).exists():
                    raise ValidationError('Identifiant indisponible ; utilisez l’ajout d’un compte existant si vous êtes autorisé')
                user=get_user_model().objects.create_user(values['username'],password=values['password'],email=values.get('email',''))
            if Membership.objects.filter(user=user,workspace=workspace).exists():
                raise ValidationError('Compte indisponible ou déjà associé à cet espace')
            row=Membership.objects.create(user=user,workspace=workspace,role=values['role'])
            AccessAudit.objects.create(user=request.user,action='membership.granted',workspace=workspace,
                metadata={'subject':user.pk,'role':row.role,'existing':values['existing']})
    except IntegrityError:
        raise ValidationError('Identifiant ou accès déjà utilisé')
    return Response(MembershipOutput(row).data,status=201)

@api_view(['PATCH'])
def update_access(request,workspace,pk):
    require_admin(request.user,workspace)
    serializer=GrantUpdate(data=request.data,context={'workspace':workspace})
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        rows=lock_admin(request.user,workspace)
        row=next((item for item in rows if item.pk==pk),None)
        if not row:return Response({'detail':'Accès introuvable dans cet espace'},status=404)
        if row.user_id==request.user.pk:
            raise ValidationError('Modification de votre propre accès interdite')
        before={'role':row.role,'active':row.active}
        client_immutable(row,serializer.validated_data.get('role',row.role))
        client_available(workspace,serializer.validated_data.get('role',row.role),exclude=row.pk)
        for key,value in serializer.validated_data.items():setattr(row,key,value)
        row.save(update_fields=list(serializer.validated_data))
        AccessAudit.objects.create(user=request.user,action='membership.updated',workspace=workspace,
            metadata={'subject':row.user_id,'before':before,'after':{'role':row.role,'active':row.active}})
    return Response(MembershipOutput(row).data)
