# ACME Inc. Product Management Application

This is a Flask-based web application designed to manage product data, including bulk CSV imports, product CRUD operations, and configurable webhooks for event notifications. It leverages Celery and Redis for asynchronous task processing, ensuring a responsive user experience even with large data sets.

## Features

*   **Bulk CSV Import:** Upload large CSV files (up to 500,000 records) to import product data. Imports are processed asynchronously in chunks to prevent timeouts and optimize memory usage.
*   **Real-time Progress Tracking:** A dynamic progress bar shows the status of ongoing CSV imports.
*   **Product CRUD:** View, create, update, and delete individual products through a web interface.
*   **Paginated Product List:** Efficiently browse product lists with pagination (100 products per page).
*   **Dynamic Sorting:** Sort product lists by various columns (SKU, Name, Description, Active status).
*   **Advanced Filtering & Search:** Filter products by specific fields (SKU, Name, Description) with options for exact or partial matches.
*   **Inline Active Status Toggle:** Quickly change a product's active/inactive status directly from the product list page.
*   **Bulk Delete Products:** Delete all products from the database with a confirmation step.
*   **Webhook Management:**
    *   Configure multiple webhooks via a UI.
    *   Define webhook URLs and event types (`product_updated`, `product_deleted`, `bulk_products_deleted`, `csv_import_complete`).
    *   Enable/disable webhooks.
    *   Asynchronous webhook testing with visual feedback (last triggered, status code, response time).
    *   Automatic triggering of webhooks on specific application events (product updates, deletions, bulk deletions, CSV import completion).
*   **Clean and Responsive UI:** A modern, tabbed interface with centralized styling for consistency.
*   **Repository Layer:** Separates business logic from data access logic for improved maintainability and testability.

## Local Development Setup

To get the application up and running on your local machine, follow these steps:

### Prerequisites

*   **Python 3.8+:** Download from [python.org](https://www.python.org/).
*   **PostgreSQL:** Database server. Download from [postgresql.org](https://www.postgresql.org/) or use Docker.
*   **Redis:** Message broker for Celery. Download from [redis.io](https://redis.io/) or use Docker.
*   **Git:** Version control.

### 1. Clone the Repository

```bash
git clone <repository_url>
cd ACME\ inc
```

### 2. Set Up a Python Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

Install all required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory of the project, based on `.env.example`.

```ini
# .env file
DATABASE_URL="postgresql://user:password@localhost:5432/acme" # Replace with your PostgreSQL connection string
SECRET_KEY="your_super_secret_key" # Change this to a strong, random key
CELERY_BROKER_URL="redis://localhost:6379/0" # Redis connection string for Celery broker
CELERY_RESULT_BACKEND="redis://localhost:6379/0" # Redis connection string for Celery results
```

*   **`DATABASE_URL`**: Ensure this points to your running PostgreSQL instance.
*   **`SECRET_KEY`**: Essential for Flask session security. Generate a strong, random string.

### 5. Database Setup

First, ensure your PostgreSQL server is running. Then, initialize the database schema:

```bash
flask init-db
```

Alternatively, you can run the SQL commands manually from the `migrations/V1__initial_schema.sql` file.

### 6. Run Redis Server

Ensure your Redis server is running and accessible at `localhost:6379`. If you're using Docker, you might start it like:

```bash
docker run -p 6379:6379 --name acme-redis -d redis
```

### 7. Run the Celery Worker

Open a **new terminal window**, activate your virtual environment, and start the Celery worker:

```bash
# On Windows, use --pool=solo
.\venv\Scripts\activate
celery -A app.celery worker --loglevel=info --pool=solo

# On macOS/Linux
source venv/bin/activate
celery -A app.celery worker --loglevel=info
```

Keep this terminal window open. This process handles all background tasks like CSV imports and webhook dispatches.

### 8. Run the Flask Application

Open another **new terminal window**, activate your virtual environment, and start the Flask development server:

```bash
# On Windows:
.\venv\Scripts\activate
flask run

# On macOS/Linux:
source venv/bin/activate
flask run
```

### 9. Access the Application

Open your web browser and navigate to `http://127.0.0.1:5000/`.

## Testing Webhooks

To test the webhook functionality:
1.  Go to `https://webhook.site/` to get a unique test URL.
2.  In your application, navigate to the "Webhooks" tab.
3.  Click "Add New Webhook" and paste your unique URL.
4.  Select an "Event Type" (e.g., `product_updated`, `product_deleted`, `bulk_products_deleted`, `csv_import_complete`).
5.  Perform the corresponding action in the app (e.g., edit a product, delete a product, bulk delete, upload CSV).
6.  Check webhook.site for incoming requests.

---

This README provides a comprehensive guide to getting the app running locally.
