"""
Custom JWT Serializers for adding groups and permissions to token claims.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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
