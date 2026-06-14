"""Celery tasks for async API operations"""
import logging
from typing import Dict, Any, Optional
from celery import Task
from services.common.celery_app import celery_app

logger = logging.getLogger("api.tasks")


class APITask(Task):
    """Base task for API operations with error handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"API task {task_id} failed: {str(exc)}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=APITask,
    name="services.api.tasks.generate_pdf_async",
    max_retries=3,
    default_retry_delay=60
)
def generate_pdf_async(self, case_id: str, case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate PDF complaint asynchronously
    
    Args:
        case_id: Case identifier
        case_data: Case data including evidence and articles
    
    Returns:
        PDF generation result
    """
    try:
        from services.database.database import get_supabase
        import httpx
        
        # Call PDF generator service
        pdf_response = httpx.post(
            os.getenv("PDF_SERVICE_URL", "http://backend:8000/pdf") + "/generate",
            json=case_data,
            timeout=60
        )
        pdf_response.raise_for_status()
        
        result = pdf_response.json()
        
        # Update case with PDF path
        db = get_supabase()
        db.table("cases").update({"pdf_path": result.get("path")}).eq("case_id", case_id).execute()
        
        return {
            "status": "success",
            "case_id": case_id,
            "pdf_path": result.get("path"),
        }
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise


@celery_app.task(
    bind=True,
    base=APITask,
    name="services.api.tasks.send_notification_async",
    max_retries=3,
    default_retry_delay=30
)
def send_notification_async(self, user_id: str, notification_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send notification to user asynchronously
    
    Args:
        user_id: User identifier
        notification_type: Type of notification (email, push, etc.)
        data: Notification data
    
    Returns:
        Notification result
    """
    try:
        # Placeholder for notification logic
        # In production, integrate with email service, push notification service, etc.
        
        logger.info(f"Sending {notification_type} notification to user {user_id}")
        
        return {
            "status": "success",
            "user_id": user_id,
            "notification_type": notification_type,
        }
        
    except Exception as e:
        logger.error(f"Notification failed: {str(e)}")
        raise


@celery_app.task(
    bind=True,
    base=APITask,
    name="services.api.tasks.cleanup_old_sessions",
    max_retries=2,
    default_retry_delay=30
)
def cleanup_old_sessions(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Clean up old chat sessions asynchronously
    
    Args:
        days_old: Delete sessions older than this many days
    
    Returns:
        Cleanup result
    """
    try:
        from services.database.database import get_supabase
        from datetime import datetime, timedelta
        
        db = get_supabase()
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        result = db.table("chat_sessions").delete().lt("created_at", cutoff_date.isoformat()).execute()
        
        return {
            "status": "success",
            "deleted_count": len(result.data) if result.data else 0,
        }
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {str(e)}")
        raise
