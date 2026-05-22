from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow read-only access to authenticated users,
    but only allow write access to admin/staff users.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class IsStaffUser(permissions.BasePermission):
    """Only allow staff users."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsLifeskillsCoach(permissions.BasePermission):
    """Allow access only to users in the 'Lifeskills Coach' group."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.groups.filter(name='Lifeskills Coach').exists()


class IsCoachOrStaff(permissions.BasePermission):
    """Allow access to staff users OR lifeskills coaches."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return request.user.groups.filter(name='Lifeskills Coach').exists()


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners or admins to edit.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        # Check if object has a user field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'participant'):
            participant = obj.participant
            if participant and hasattr(participant, 'user'):
                return participant.user == request.user
        return False


class ReadOnlyPermission(permissions.BasePermission):
    """Only allow read operations - for log models."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in permissions.SAFE_METHODS


class IsSingletonAdmin(permissions.BasePermission):
    """
    Permission for singleton models.
    Only staff can modify, anyone authenticated can read.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_staff


class CanBypassOrderTransitions(permissions.BasePermission):
    """
    Allow a user to move orders between any active status
    (confirmed ↔ packing ↔ completed) regardless of the normal
    forward-only transition rules.

    Granted to:
    - Superusers automatically (Django short-circuits has_perm for them)
    - Any user explicitly assigned the 'orders.can_bypass_order_transitions' permission
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_perm('orders.can_bypass_order_transitions')
