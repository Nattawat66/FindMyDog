# myapp/cron.py
import logging
from myapp.serverFast import trainKNN  # หรือ import ตามจริง

logger = logging.getLogger(__name__)

def trainKNN_job():
    logger.info("Cron started: trainKNN_job")
    result = trainKNN()
    logger.info(f"Cron finished: {result}")
