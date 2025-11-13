import pandas as pd
import math
import requests
import time
from celery import shared_task
from repositories import ProductRepository, WebhookRepository
from extensions import db

def get_total_rows(filepath):
    """Helper function to get total number of rows in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        # The -1 is to account for the header row
        return sum(1 for row in f) -1

@shared_task(bind=True, ignore_result=False)
def import_products_task(self, filepath):
    """
    Background task to import products from a CSV file.
    Delegates the database logic to the ProductRepository.
    """
    from app import app # lazy import
    
    product_repo = ProductRepository()
    CHUNK_SIZE = 1000
    
    try:
        total_rows = get_total_rows(filepath)
        processed_rows = 0
        self.update_state(state='PROGRESS', meta={'status': 'Starting import...', 'progress': 0})
        
        with app.app_context():
            # Process file in chunks
            for chunk in pd.read_csv(filepath, chunksize=CHUNK_SIZE, keep_default_na=False):
                # Normalize column names
                chunk.columns = [col.lower().strip() for col in chunk.columns]
                
                # Ensure required columns exist
                if 'sku' not in chunk.columns:
                    raise KeyError("CSV must contain a 'sku' column.")

                # Delegate the database work to the repository
                product_repo.bulk_upsert(chunk)
                
                # Update progress
                processed_rows += len(chunk)
                progress = math.ceil((processed_rows / total_rows) * 100) if total_rows > 0 else 100
                self.update_state(state='PROGRESS', meta={'status': f'Processing... {processed_rows}/{total_rows} rows', 'progress': progress})

            # Commit the transaction after all chunks are processed
            db.session.commit()

            # Dispatch webhook for csv_import_complete event
            payload = {
                "event": "csv_import_complete",
                "message": "CSV import finished successfully.",
                "total_rows_processed": processed_rows,
                "filepath": filepath # Or just the filename
            }
            send_webhook_event_task.delay('csv_import_complete', payload)

    except (FileNotFoundError, KeyError) as e:
        db.session.rollback()
        self.update_state(state='FAILURE', meta={'status': f'Error: {e}'})
        # Dispatch webhook for csv_import_failed event (optional, but good practice)
        send_webhook_event_task.delay('csv_import_failed', {
            "event": "csv_import_failed",
            "message": f"CSV import failed: {e}",
            "filepath": filepath
        })
        raise
    except Exception as e:
        db.session.rollback()
        self.update_state(state='FAILURE', meta={'status': f'An unexpected error occurred: {e}'})
        # Dispatch webhook for csv_import_failed event
        send_webhook_event_task.delay('csv_import_failed', {
            "event": "csv_import_failed",
            "message": f"CSV import failed due to an unexpected error: {e}",
            "filepath": filepath
        })
        raise

    return {'status': 'Import complete!', 'progress': 100}


@shared_task(ignore_result=True)
def send_webhook_event_task(event_type, payload):
    """
    Background task to send webhooks for a specific event type.
    """
    from app import app # lazy import
    webhook_repo = WebhookRepository()
    
    with app.app_context():
        # Get all enabled webhooks for this event type
        webhooks = webhook_repo.get_all_enabled_for_event(event_type)
        
        for webhook in webhooks:
            status_code = None
            response_time = None
            try:
                start_time = time.monotonic()
                response = requests.post(
                    webhook.url, 
                    json=payload,
                    timeout=10 # Longer timeout for actual events
                )
                end_time = time.monotonic()
                status_code = response.status_code
                response_time = (end_time - start_time) * 1000 # in milliseconds

            except requests.exceptions.RequestException as e:
                status_code = 0 # Indicate a connection/request error
                response_time = 0.0
                print(f"Webhook send failed for {webhook.url} (Event: {event_type}): {e}")
            finally:
                webhook_repo.update_last_trigger_status(webhook, status_code, response_time)

@shared_task(ignore_result=True)
def test_webhook_task(webhook_id):
    """
    Background task to test a webhook by sending a POST request
    and updating its last triggered status.
    """
    from app import app # lazy import
    webhook_repo = WebhookRepository() # Instantiate inside task
    
    with app.app_context():
        webhook = webhook_repo.get_by_id(webhook_id)
        if webhook and webhook.enabled:
            status_code = None
            response_time = None
            try:
                start_time = time.monotonic()
                response = requests.post(
                    webhook.url, 
                    json={"test_event": webhook.event_type, "timestamp": time.time()},
                    timeout=5 # Timeout after 5 seconds
                )
                end_time = time.monotonic()
                status_code = response.status_code
                response_time = (end_time - start_time) * 1000 # in milliseconds

            except requests.exceptions.RequestException as e:
                # Handle connection errors, timeouts, etc.
                status_code = 0 # Indicate a connection error
                response_time = 0.0
                print(f"Webhook test failed for {webhook.url}: {e}")
            finally:
                # Update webhook status in DB
                webhook_repo.update_last_trigger_status(webhook, status_code, response_time)