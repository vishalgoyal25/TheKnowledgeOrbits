"""
Authorization Engine - RBAC Middleware

Attaches user roles to request object for easy access.
"""

from django.utils.deprecation import MiddlewareMixin


class RBACMiddleware(MiddlewareMixin):
    """
    Middleware to attach user roles to request.
    
    After this middleware, you can access:
        - request.user_roles (list of role names)
        - request.is_admin (boolean)
        - request.is_content_manager (boolean)
    """
    
    def process_request(self, request):
        """Attach role information to request."""
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Get user's roles
            user_roles = list(
                request.user.role_assignments.values_list('role__name', flat=True)
            )
            
            # Attach to request
            request.user_roles = user_roles
            request.is_admin = 'admin' in user_roles
            request.is_content_manager = 'content_manager' in user_roles
            request.is_student = 'student' in user_roles
            request.is_free_user = 'free_user' in user_roles
        else:
            # Anonymous user
            request.user_roles = []
            request.is_admin = False
            request.is_content_manager = False
            request.is_student = False
            request.is_free_user = False
        
        return None

        