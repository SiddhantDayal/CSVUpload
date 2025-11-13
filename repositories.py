from extensions import db
from models import Product, Webhook # Import Webhook model
from sqlalchemy import or_, func
from datetime import datetime

class ProductRepository:
    # ... (existing ProductRepository code)
    def get_by_id(self, product_id):
        """Fetches a product by its ID."""
        return Product.query.get_or_404(product_id)

    def list_paginated(self, page, per_page, filters):
        """
        Fetches a paginated, filtered, and sorted list of products.
        'filters' is a dict containing all search/sort/filter parameters.
        """
        query = Product.query

        # Status filter
        active_filter = filters.get('active_filter', 'all')
        if active_filter == 'active':
            query = query.filter(Product.active.is_(True))
        elif active_filter == 'inactive':
            query = query.filter(Product.active.is_(False))

        # Advanced search filter
        search_field = filters.get('search_field')
        search_value = filters.get('search_value')
        exact_match = filters.get('exact_match')
        allowed_fields = ['sku', 'name', 'description']
        if search_field in allowed_fields and search_value:
            search_column = getattr(Product, search_field)
            if exact_match:
                query = query.filter(search_column == search_value)
            else:
                query = query.filter(search_column.ilike(f"%{search_value}%"))

        # Sorting
        sort_by = filters.get('sort_by', 'name')
        sort_order = filters.get('sort_order', 'asc')
        if sort_by not in ['sku', 'name', 'description', 'active']:
            sort_by = 'name'
        sort_column = getattr(Product, sort_by)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query.paginate(page=page, per_page=per_page)

    def bulk_upsert(self, chunk):
        """
        Performs a bulk "upsert" operation for a chunk of product data.
        Updates existing products and inserts new ones.
        """
        # Normalize SKU data for case-insensitive comparison
        chunk['sku_upper'] = chunk['sku'].str.upper()
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

        # The session is committed outside, after all chunks are processed,
        # or within the task itself. For now, we assume the caller handles the commit.
        # This can be adjusted if each chunk should be a separate transaction.

    def update(self, product, data):
        """Updates a product with new data."""
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.active = data.get('active', product.active)
        db.session.commit()
        return product

    def delete(self, product):
        """Deletes a product."""
        db.session.delete(product)
        db.session.commit()

    def delete_all(self):
        """Deletes all products."""
        db.session.query(Product).delete()
        db.session.commit()
    
    def toggle_active(self, product):
        """Toggles the active status of a product."""
        product.active = not product.active
        db.session.commit()
        return product


class WebhookRepository:
    def create(self, url, event_type, enabled=True):
        webhook = Webhook(url=url, event_type=event_type, enabled=enabled)
        db.session.add(webhook)
        db.session.commit()
        return webhook

    def get_by_id(self, webhook_id):
        return Webhook.query.get_or_404(webhook_id)

    def get_all_enabled(self):
        return Webhook.query.filter_by(enabled=True).all()

    def get_all_enabled_for_event(self, event_type):
        """Retrieves all enabled webhooks for a specific event type."""
        return Webhook.query.filter_by(enabled=True, event_type=event_type).all()

    def list_paginated(self, page, per_page, filters):
        query = Webhook.query

        # Basic filtering for event_type if needed
        event_type_filter = filters.get('event_type_filter')
        if event_type_filter and event_type_filter != 'all':
            query = query.filter_by(event_type=event_type_filter)

        # Basic sorting
        sort_by = filters.get('sort_by', 'id')
        sort_order = filters.get('sort_order', 'asc')
        if sort_by not in ['id', 'url', 'event_type', 'enabled', 'last_triggered', 'last_status_code', 'last_response_time']:
            sort_by = 'id'
        sort_column = getattr(Webhook, sort_by)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        return query.paginate(page=page, per_page=per_page)

    def update(self, webhook, data):
        webhook.url = data.get('url', webhook.url)
        webhook.event_type = data.get('event_type', webhook.event_type)
        webhook.enabled = data.get('enabled', webhook.enabled)
        db.session.commit()
        return webhook

    def delete(self, webhook):
        db.session.delete(webhook)
        db.session.commit()

    def toggle_enabled(self, webhook):
        webhook.enabled = not webhook.enabled
        db.session.commit()
        return webhook

    def update_last_trigger_status(self, webhook, status_code, response_time):
        webhook.last_triggered = datetime.utcnow()
        webhook.last_status_code = status_code
        webhook.last_response_time = response_time
        db.session.commit()
        return webhook
