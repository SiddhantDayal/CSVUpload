from extensions import db
from models import Webhook # Import Webhook model
from sqlalchemy import or_, func
from datetime import datetime


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