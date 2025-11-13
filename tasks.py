import pandas as pd
import math
from celery import shared_task
from repositories import ProductRepository
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

    except (FileNotFoundError, KeyError) as e:
        db.session.rollback()
        self.update_state(state='FAILURE', meta={'status': f'Error: {e}'})
        raise
    except Exception as e:
        db.session.rollback()
        self.update_state(state='FAILURE', meta={'status': f'An unexpected error occurred: {e}'})
        raise

    return {'status': 'Import complete!', 'progress': 100}