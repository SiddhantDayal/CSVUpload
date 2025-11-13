from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from extensions import db, make_celery
import os, uuid
from dotenv import load_dotenv

from tasks import import_products_task
from repositories import ProductRepository # Import the repository

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

    task = import_products_task.delay(filepath)
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

@app.route("/products")
def list_products():
    page = request.args.get('page', 1, type=int)
    # Consolidate all filter, sort, and search params into a single dict
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
        product_repo.toggle_active(product)
        return jsonify({'success': True, 'new_status': product.active})
    except Exception as e:
        # The session rollback should ideally be handled within the repository
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/products/delete-all", methods=["POST"])
def delete_all_products():
    try:
        product_repo.delete_all()
        flash("All products have been successfully deleted.", "success")
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
            product_repo.update(product, update_data)
            flash("Product updated successfully!", "success")
            return redirect(url_for("list_products"))
        except Exception as e:
            flash(f"Error updating product: {e}", "error")
    return render_template("edit_product.html", product=product)

@app.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    product = product_repo.get_by_id(product_id)
    try:
        product_repo.delete(product)
        flash("Product deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting product: {e}", "error")
    return redirect(url_for("list_products"))

# --- CLI COMMANDS ---
@app.cli.command("init-db")
def init_db():
    """Clear existing data and create new tables."""
    db.create_all()
    print("Initialized the database.")

if __name__ == "__main__":
    app.run(debug=True)