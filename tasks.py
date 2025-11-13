import pandas as pd
from sqlalchemy import func
from extensions import db
from models import Product

def import_products_task(filepath):
    """
    Synchronous task to import products from a CSV file.
    This task is designed to be memory-efficient by processing the file in chunks.
    It performs an "upsert" operation: updating existing products and inserting new ones.
    """
    CHUNK_SIZE = 1000
    try:
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

    except (FileNotFoundError, KeyError) as e:
        # Re-raise exceptions to be caught by the calling route
        raise e
    except Exception as e:
        raise e

    return "Import complete!"
