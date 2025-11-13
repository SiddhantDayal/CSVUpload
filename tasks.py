from app import celery
import time, redis

r = redis.Redis(host="localhost", port=6379, db=0)

@celery.task(bind=True)
def import_products_task(self, filepath):
    for i in range(1, 11):
        time.sleep(1)
        r.set(self.request.id, str(i * 10))
    return {"status": "Completed", "file": filepath}
