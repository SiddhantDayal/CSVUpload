import pandas as pd
import math
from sqlalchemy import func
from extensions import db
from models import Product
from celery import shared_task

def get_total_rows(filepath):
    """Helper function to get total number of rows in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        # The -1 is to account for the header row
        return sum(1 for row in f) -1

@shared_task(bind=True, ignore_result=False)
def import_products_task(self, filepath):
    """
    Background task to import products from a CSV file.
    This task is designed to be memory-efficient by processing the file in chunks.
    It performs an "upsert" operation: updating existing products and inserting new ones.
    """
    from app import app # lazy import
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

                # Normalize SKU data for case-insensitive comparison
                chunk['sku_upper'] = chunk['sku'].str.upper()
                
                # Get SKUs from the current chunk
                chunk_skus = chunk['sku_upper'].tolist()
                
                # Find existing products in the DB that match SKUs from the chunk
                existing_products = Product.query.filter(func.upper(Product.sku).in_(chunk_skus)).all()
                sku_to_product = {product.sku.upper(): product for product in existing_products}

                products_to_add_map = {} # Use a map to handle in-chunk duplicates
                
                for _, row in chunk.iterrows():
                    sku_upper = row['sku_upper']
                    
                    product = sku_to_product.get(sku_upper)
                    
                    # Prepare product data from the row
                    product_data = {
                        'name': row.get('name', ''),
                        'description': row.get('description', ''),
                        'active': True # Set as active on import/update
                    }

                    if product:
                        # Update existing product
                        product.name = product_data['name']
                        product.description = product_data['description']
                        product.active = product_data['active']
                    else:
                        # Stage new product for insertion, overwriting duplicates in the same chunk
                        product_data['sku'] = row['sku'] # Use original SKU
                        products_to_add_map[sku_upper] = product_data

                # Bulk insert new products
                if products_to_add_map:
                    db.session.bulk_insert_mappings(Product, products_to_add_map.values())

                # Commit session to save updates and new inserts
                db.session.commit()
                
                # Update progress
                processed_rows += len(chunk)
                progress = math.ceil((processed_rows / total_rows) * 100) if total_rows > 0 else 100
                self.update_state(state='PROGRESS', meta={'status': f'Processing... {processed_rows}/{total_rows} rows', 'progress': progress})

    except (FileNotFoundError, KeyError) as e:
        self.update_state(state='FAILURE', meta={'status': f'Error: {e}'})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'An unexpected error occurred: {e}'})
        raise

    return {'status': 'Import complete!', 'progress': 100}
