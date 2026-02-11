"""
Custom JWT Serializers for adding groups and permissions to token claims.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.contrib.auth.models import User


class FlexibleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT serializer that accepts either customer_number or username for authentication.
    
    Authentication Flow:
    1. Check if input looks like customer_number (format: C-XXX-D)
    2. If yes, look up Participant → User
    3. If no, use standard username authentication
    4. Validate password for found user
    
    Error codes returned:
    - customer_not_found: Customer number doesn't exist
    - username_not_found: Username doesn't exist  
    - no_user_account: Participant exists but no user account linked
    - invalid_password: Password is incorrect
    - account_disabled: User account is inactive
    """
    
    def validate(self, attrs):
        """Custom validation to handle customer_number or username login."""
        identifier = attrs.get('username', '')
        password = attrs.get('password', '')
        
        user = None
        
        # Check if identifier looks like customer number (C-XXX-D format)
        if identifier.startswith('C-') and len(identifier) >= 7:
            # Customer number login
            from apps.account.models import Participant
            
            try:
                participant = Participant.objects.select_related('user').get(
                    customer_number=identifier.upper()
                )
                
                if not participant.user:
                    raise AuthenticationFailed({
                        'detail': 'No user account linked to this customer number.',
                        'code': 'no_user_account'
                    })
                
                user = participant.user
                
            except Participant.DoesNotExist:
                raise AuthenticationFailed({
                    'detail': 'Customer number not found.',
                    'code': 'customer_not_found'
                })
        else:
            # Standard username login
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                raise AuthenticationFailed({
                    'detail': 'Username not found.',
                    'code': 'username_not_found'
                })
        
        # Validate password
        if user and not user.check_password(password):
            raise AuthenticationFailed({
                'detail': 'Incorrect password.',
                'code': 'invalid_password'
            })
        
        if not user or not user.is_active:
            raise AuthenticationFailed({
                'detail': 'Account is disabled.',
                'code': 'account_disabled'
            })
        
        # Set the user for token generation
        self.user = user
        
        # Generate tokens
        refresh = self.get_token(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        # Add user info to response with participant data
        from apps.account.models import Participant
        participant = None
        try:
            participant = Participant.objects.get(user=user)
        except Participant.DoesNotExist:
            pass
        
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'participant_id': participant.id if participant else None,
            'customer_number': participant.customer_number if participant else None,
            'name': participant.name if participant else f"{user.first_name} {user.last_name}".strip(),
        }
        
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that adds user metadata to token claims.
    
    Adds:
    - username, email
    - is_staff, is_superuser (for quick permission checks)
    - groups (list of group names)
    - group_ids (list of group IDs for efficient lookups)
    """
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Basic user info
        token['username'] = user.username
        token['email'] = user.email if user.email else ''
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        
        # Groups (lightweight role indicators)
        groups = user.groups.all()
        token['groups'] = [g.name for g in groups]
        token['group_ids'] = [g.id for g in groups]
        
        return token
    
    def validate(self, attrs):
        """Add user info to response (not in token, just response)."""
        data = super().validate(attrs)
        
        # Add user info to login response
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
        }
        
        return data
