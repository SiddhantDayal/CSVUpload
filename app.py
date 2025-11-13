from flask import Flask, render_template, request, flash, redirect, url_for
from extensions import db
import os, uuid

from tasks import import_products_task
from models import Product # Import Product model

app = Flask(__name__)

app.config.update(
    SQLALCHEMY_DATABASE_URI="sqlite:///acme.db",
    UPLOAD_FOLDER=os.path.join(os.getcwd(), "uploads"),
    SECRET_KEY='your_secret_key' # Needed for flashing messages
)

db.init_app(app)

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload", methods=["POST"])
def upload_csv():
    file = request.files.get("file")
    if not file:
        flash("No file provided.", "error")
        return redirect(url_for('home'))

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = f"{uuid.uuid4()}.csv"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        with app.app_context():
            result_message = import_products_task(filepath)
        flash(result_message, "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "error")
    
    return redirect(url_for('home'))

@app.route("/products")
def list_products():
    products = Product.query.all()
    return render_template("products.html", products=products)

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
