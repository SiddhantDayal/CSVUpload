from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from extensions import db, make_celery
import os, uuid
from dotenv import load_dotenv

from tasks import import_products_task
from models import Product # Import Product model

load_dotenv()

app = Flask(__name__)

app.config.update(
    # Change to PostgreSQL. 
    # The user should set the DATABASE_URL environment variable.
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/acme"),
    UPLOAD_FOLDER=os.path.join(os.getcwd(), "uploads"),
    SECRET_KEY=os.environ.get("SECRET_KEY", "super_secret_dev_key"), # Read from environment, with a dev default
    CELERY_BROKER_URL=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    CELERY_RESULT_BACKEND=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

db.init_app(app)
celery = make_celery(app)

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
    if task.state == 'PENDING':
        # Job did not start yet
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.info.get('status', ''),
        }
        if 'progress' in task.info:
            response['progress'] = task.info['progress']
    else:
        # Something went wrong in the background job
        response = {
            'state': task.state,
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)

@app.route("/products")
def list_products():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'name', type=str) # Default sort to 'name'
    sort_order = request.args.get('sort_order', 'asc', type=str)
    
    # Advanced search parameters
    search_field = request.args.get('search_field', 'name', type=str) # Default search field to 'name'
    search_value = request.args.get('search_value', '', type=str)
    exact_match = request.args.get('exact_match', type=bool)
    active_filter = request.args.get('active_filter', 'all', type=str) # New filter

    query = Product.query

    # Status filter
    if active_filter == 'active':
        query = query.filter(Product.active.is_(True))
    elif active_filter == 'inactive':
        query = query.filter(Product.active.is_(False))

    # Advanced search filter
    allowed_fields = ['sku', 'name', 'description'] # Removed 'id'
    if search_field in allowed_fields and search_value:
        search_column = getattr(Product, search_field)
        if exact_match:
            query = query.filter(search_column == search_value)
        else:
            query = query.filter(search_column.ilike(f"%{search_value}%"))

    # Validate sort_by parameter
    if sort_by not in ['sku', 'name', 'description', 'active']: # Re-added 'active'
        sort_by = 'name' # Fallback to 'name'
    
    sort_column = getattr(Product, sort_by)

    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    products = query.paginate(page=page, per_page=100)
    
    return render_template("products.html", 
                           products=products, 
                           sort_by=sort_by, 
                           sort_order=sort_order,
                           search_field=search_field,
                           search_value=search_value,
                           exact_match=exact_match,
                           active_filter=active_filter, # Pass to template
                           active_page="products")

@app.route("/products/<int:product_id>/toggle-active", methods=["POST"])
def toggle_active(product_id):
    """Toggles the active status of a product."""
    product = Product.query.get_or_404(product_id)
    try:
        product.active = not product.active
        db.session.commit()
        return jsonify({'success': True, 'new_status': product.active})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route("/products/delete-all", methods=["POST"])
def delete_all_products():
    """Deletes all products from the database."""
    try:
        # Efficiently delete all rows
        db.session.query(Product).delete()
        db.session.commit()
        flash("All products have been successfully deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while deleting products: {e}", "error")
    return redirect(url_for('list_products'))

@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        product.name = request.form["name"]
        product.description = request.form["description"]
        product.active = "active" in request.form # Checkbox value presence
        try:
            db.session.commit()
            flash("Product updated successfully!", "success")
            return redirect(url_for("list_products"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating product: {e}", "error")
    return render_template("edit_product.html", product=product)

@app.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting product: {e}", "error")
    return redirect(url_for("list_products"))

@app.cli.command("init-db")
def init_db():
    """Clear existing data and create new tables."""
    db.create_all()
    print("Initialized the database.")

if __name__ == "__main__":
    app.run(debug=True)
