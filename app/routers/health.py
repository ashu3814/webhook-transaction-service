from fastapi import APIRouter
from app.utils.logger import logger
from app.utils.time import now_ist
import os
import time
import psutil
from datetime import datetime
from app.database import SessionLocal
from app.tasks.celery_app import celery_app

router = APIRouter(tags=["health"])

# Track server start time
SERVER_START_TIME = time.time()

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "CELERY_BROKER_URL", 
    "CELERY_RESULT_BACKEND",
    "API_ENV",
    "API_HOST",
    "API_PORT"
]

def check_env_variables():
    """Check if all required env variables are set"""
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(var)
    return missing

def check_database():
    """Check if database is connected"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True, None
    except Exception as e:
        return False, str(e)

def check_celery():
    """Check if Celery worker is connected"""
    try:
        result = celery_app.control.inspect().active()
        if result:
            return True, None
        else:
            return False, "No workers responding"
    except Exception as e:
        return False, str(e)

def get_server_uptime():
    """Get server uptime in seconds"""
    return time.time() - SERVER_START_TIME

def get_process_info():
    """Get current process memory and CPU usage"""
    try:
        process = psutil.Process(os.getpid())
        memory = process.memory_info().rss / 1024 / 1024  # MB
        cpu_percent = process.cpu_percent(interval=0.1)
        return {
            "memory_mb": round(memory, 2),
            "cpu_percent": round(cpu_percent, 2)
        }
    except:
        return None

@router.get("/")
async def health_check():
    """
    Complete server health check with real-time diagnostics
    Shows: Server status, errors, database, celery, resources
    """
    
    # Run all checks
    missing_env = check_env_variables()
    db_ok, db_error = check_database()
    celery_ok, celery_error = check_celery()
    uptime = get_server_uptime()
    process_info = get_process_info()
    
    # Determine overall status
    if missing_env:
        status = "ERROR"
        error_message = f"Missing environment variables: {', '.join(missing_env)}"
    elif not db_ok:
        status = "ERROR"
        error_message = f"Database connection failed: {db_error}"
    elif not celery_ok:
        status = "WARNING"
        error_message = f"Celery worker not responding: {celery_error}"
    else:
        status = "RUNNING"
        error_message = None
    
    # Build response
    response = {
        "server": {
            "status": status,
            "current_time": now_ist().isoformat(),
            "uptime_seconds": round(uptime, 2),
            "environment": os.getenv("API_ENV", "unknown")
        },
        "checks": {
            "environment": {
                "ok": len(missing_env) == 0,
                "missing_vars": missing_env
            },
            "database": {
                "ok": db_ok,
                "error": db_error
            },
            "celery_worker": {
                "ok": celery_ok,
                "error": celery_error
            }
        },
        "resources": process_info,
        "error": error_message
    }
    
    # Log status
    if status == "ERROR":
        logger.error("Health check failed: %s", error_message)
    elif status == "WARNING":
        logger.warning("Health check warning: %s", error_message)
    else:
        logger.info("Health check passed status=%s", status)
    
    return response