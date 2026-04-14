import uuid
from .models import ActivityLog, Admin

def log_activity(request, action, target=None, description=None):
    """
    Utility function to log administrative actions.
    Records the admin performing the action, the target of the action,
    and a description.
    """
    admin_id = request.session.get('admin_id')
    admin = None
    if admin_id:
        try:
            admin = Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            pass
    
    # IP Address logging removed as per user request (Privacy)

    ActivityLog.objects.create(
        id=uuid.uuid4(),
        admin=admin,
        action=action,
        target=target,
        description=description
    )
