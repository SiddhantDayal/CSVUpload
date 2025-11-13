from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from extensions import db, make_celery
import os, uuid
from dotenv import load_dotenv

import tasks # Import the entire tasks module
from repositories import ProductRepository, WebhookRepository # Import both repositories

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
app.config.update(
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/acme"),
    UPLOAD_FOLDER=os.path.join(os.getcwd(), "uploads"),
    SECRET_KEY=os.environ.get("SECRET_KEY", "super_secret_dev_key"),
    CELERY_BROKER_URL=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    CELERY_RESULT_BACKEND=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

# --- EXTENSIONS ---
db.init_app(app)
celery = make_celery(app)

# --- REPOSITORIES ---
product_repo = ProductRepository()
webhook_repo = WebhookRepository() # Instantiate WebhookRepository

# --- ROUTES ---
@app.route("/")
def home():
    return render_template("upload.html", active_page="upload")

@app.route("/upload", methods=["POST"])
def upload_csv():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = f"{uuid.uuid4()}.csv"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    task = tasks.import_products_task.delay(filepath) # Assign the result to 'task'
    return jsonify({"task_id": task.id})

@app.route("/status/<task_id>")
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    response_data = {'state': task.state, 'status': str(task.info)}
    if task.state == 'PENDING':
        response_data['status'] = 'Pending...'
    elif task.state != 'FAILURE':
        response_data.update(task.info)
    return jsonify(response_data)

# --- Product Routes ---
@app.route("/products")
def list_products():
    page = request.args.get('page', 1, type=int)
    filters = {
        'sort_by': request.args.get('sort_by', 'name', type=str),
        'sort_order': request.args.get('sort_order', 'asc', type=str),
        'search_field': request.args.get('search_field', 'name', type=str),
        'search_value': request.args.get('search_value', '', type=str),
        'exact_match': request.args.get('exact_match', type=bool),
        'active_filter': request.args.get('active_filter', 'all', type=str)
    }
    
    products = product_repo.list_paginated(page=page, per_page=100, filters=filters)
    
    return render_template("products.html", 
                           products=products, 
                           active_page="products",
                           **filters)

@app.route("/products/<int:product_id>/toggle-active", methods=["POST"])
def toggle_active(product_id):
    product = product_repo.get_by_id(product_id)
    try:
        # Capture old data before toggle
        old_product_data = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "active": product.active
        }

        product_repo.toggle_active(product) # This updates the product.active state

        # Capture new data after toggle
        new_product_data = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "active": product.active
        }
        
        # Dispatch webhook for product_updated event with consistent structure
        payload = {
            "event": "product_updated",
            "product_id": product.id,
            "changes": {
                "old_data": old_product_data,
                "new_data": new_product_data
            }
        }
        tasks.send_webhook_event_task.delay('product_updated', payload)

        return jsonify({'success': True, 'new_status': product.active})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/products/delete-all", methods=["POST"])
def delete_all_products():
    try:
        # Optionally, count products before deletion if you want that in payload
        # product_count = product_repo.get_count()

        product_repo.delete_all()
        flash("All products have been successfully deleted.", "success")
        
        # Dispatch webhook for bulk_products_deleted event
        payload = {
            "event": "bulk_products_deleted",
            "message": "All products in the database have been deleted.",
            # "deleted_count": product_count # if captured above
        }
        tasks.send_webhook_event_task.delay('bulk_products_deleted', payload)

    except Exception as e:
        flash(f"An error occurred while deleting products: {e}", "error")
    return redirect(url_for('list_products'))

@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = product_repo.get_by_id(product_id)
    if request.method == "POST":
        try:
            update_data = {
                "name": request.form["name"],
                "description": request.form["description"],
                "active": "active" in request.form
            }
            # Store old data before update for potential webhook payload
            old_product_data = {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "description": product.description,
                "active": product.active
            }

            product_repo.update(product, update_data)
            flash("Product updated successfully!", "success")

            # Dispatch webhook for product_updated event
            payload = {
                "event": "product_updated",
                "product_id": product.id,
                "changes": {
                    "old_data": old_product_data,
                    "new_data": {
                        "id": product.id,
                        "sku": product.sku,
                        "name": product.name,
                        "description": product.description,
                        "active": product.active
                    }
                }
            }
            tasks.send_webhook_event_task.delay('product_updated', payload) # Use tasks.send_webhook_event_task

            redirect_args = {k: v for k, v in request.form.items() if k not in ['name', 'description', 'active', 'csrf_token']}
            return redirect(url_for("list_products", **redirect_args))
        except Exception as e:
            flash(f"Error updating product: {e}", "error")
    return render_template("edit_product.html", product=product)

@app.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    product = product_repo.get_by_id(product_id)
    try:
        # Capture data of the product about to be deleted
        deleted_product_data = {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "active": product.active
        }

        product_repo.delete(product)
        flash("Product deleted successfully!", "success")

        # Dispatch webhook for product_deleted event
        payload = {
            "event": "product_deleted",
            "product_id": deleted_product_data["id"],
            "deleted_data": deleted_product_data
        }
        tasks.send_webhook_event_task.delay('product_deleted', payload)

    except Exception as e:
        flash(f"Error deleting product: {e}", "error")
    return redirect(url_for("list_products"))

# --- Webhook Routes ---
@app.route("/webhooks")
def list_webhooks():
    page = request.args.get('page', 1, type=int)
    filters = {
        'sort_by': request.args.get('sort_by', 'id', type=str),
        'sort_order': request.args.get('sort_order', 'asc', type=str),
        'event_type_filter': request.args.get('event_type_filter', 'all', type=str)
    }
    webhooks = webhook_repo.list_paginated(page=page, per_page=10, filters=filters) # 10 webhooks per page
    
    # Define possible event types for the filter dropdown
    event_types = sorted(list(set([wh.event_type for wh in webhook_repo.get_all_enabled()]))) # Get all unique event types
    if not event_types: # Fallback if no webhooks exist yet
        event_types = ['product_updated', 'csv_import_complete', 'product_deleted', 'bulk_products_deleted']

    return render_template("webhooks.html", 
                           webhooks=webhooks, 
                           event_types=event_types,
                           active_page="webhooks",
                           **filters)

@app.route("/webhooks/add", methods=["GET", "POST"])
def add_webhook():
    if request.method == "POST":
        url = request.form["url"]
        event_type = request.form["event_type"]
        enabled = "enabled" in request.form
        try:
            webhook_repo.create(url=url, event_type=event_type, enabled=enabled)
            flash("Webhook added successfully!", "success")
            return redirect(url_for("list_webhooks"))
        except Exception as e:
            flash(f"Error adding webhook: {e}", "error")
    possible_event_types = ['product_updated', 'csv_import_complete', 'product_deleted', 'bulk_products_deleted']
    return render_template("add_edit_webhook.html", 
                           active_page="webhooks", 
                           title="Add Webhook", 
                           possible_event_types=possible_event_types)

@app.route("/webhooks/<int:webhook_id>/edit", methods=["GET", "POST"])
def edit_webhook(webhook_id):
    webhook = webhook_repo.get_by_id(webhook_id)
    if request.method == "POST":
        try:
            update_data = {
                "url": request.form["url"],
                "event_type": request.form["event_type"],
                "enabled": "enabled" in request.form
            }
            webhook_repo.update(webhook, update_data)
            flash("Webhook updated successfully!", "success")
            return redirect(url_for("list_webhooks"))
        except Exception as e:
            flash(f"Error updating webhook: {e}", "error")
    possible_event_types = ['product_updated', 'csv_import_complete', 'product_deleted', 'bulk_products_deleted']
    return render_template("add_edit_webhook.html", 
                           active_page="webhooks", 
                           title="Edit Webhook", 
                           webhook=webhook, 
                           possible_event_types=possible_event_types)

@app.route("/webhooks/<int:webhook_id>/delete", methods=["POST"])
def delete_webhook(webhook_id):
    webhook = webhook_repo.get_by_id(webhook_id)
    try:
        webhook_repo.delete(webhook)
        flash("Webhook deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting webhook: {e}", "error")
    return redirect(url_for("list_webhooks"))

@app.route("/webhooks/<int:webhook_id>/toggle-enabled", methods=["POST"])
def toggle_webhook_enabled(webhook_id):
    webhook = webhook_repo.get_by_id(webhook_id)
    try:
        webhook_repo.toggle_enabled(webhook)
        return jsonify({'success': True, 'new_status': webhook.enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/webhooks/<int:webhook_id>/test", methods=["POST"])
def test_webhook(webhook_id):
    try:
        # Queue the test webhook task
        tasks.test_webhook_task.delay(webhook_id) # Use tasks.test_webhook_task
        return jsonify({'success': True, 'message': 'Webhook test initiated successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- CLI COMMANDS ---
@app.cli.command("init-db")
def init_db():
    """Clear existing data and create new tables."""
    db.create_all()
    print("Initialized the database.")

if __name__ == "__main__":
    app.run(debug=True)