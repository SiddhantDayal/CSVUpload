# ACME Inc. Product Management Application

This is a Flask-based web application designed to manage product data, including bulk CSV imports, product CRUD operations, and configurable webhooks for event notifications. It leverages Celery and Redis for asynchronous task processing, ensuring a responsive user experience even with large data sets.

## Overall Features

*   **Bulk CSV Import:** Upload large CSV files (up to 500,000 records) to import product data. Imports are processed asynchronously in chunks to prevent timeouts and optimize memory usage. The UI provides real-time progress tracking.
*   **Persistent Upload Status:** If you navigate away from the upload page, the app remembers and displays the status of the last upload when you return.
*   **Product Management (CRUD):** View, create, update, and delete individual products through a dedicated web interface.
*   **Efficient Product Listing:** Products are displayed with pagination (100 products per page), dynamic sorting by various columns (SKU, Name, Description, Active status), and advanced filtering/searching capabilities (exact or partial matches on selected fields).
*   **Inline Active Status Toggle:** Quickly change a product's active/inactive status directly from the product list page.
*   **Bulk Delete Products:** Delete all products from the database with a confirmation step.
*   **Webhook Management:** Configure, add, edit, test, and delete webhooks via a UI. Webhooks can be enabled/disabled and automatically trigger on application events like `product_created`, `product_updated`, `product_deleted`, `bulk_products_deleted`, and `csv_import_complete`. Asynchronous testing provides visual feedback (last triggered, status code, response time).
*   **Clean and Responsive UI:** A modern, tabbed interface with centralized styling for consistency.
*   **Repository Layer:** A dedicated repository pattern separates business logic from data access logic, enhancing maintainability and testability.

## Data Flow in the Application

The application is structured as a multi-service architecture, leveraging a web frontend, background workers, a relational database, and an in-memory message broker/cache.

1.  **User Interaction (Flask Web App):**
    *   **File Upload:** A user uploads a CSV file through the web UI. The Flask app saves this file to a shared `uploads` directory.
    *   **Task Dispatch:** Instead of processing the file immediately, the Flask app dispatches a Celery task (`import_products_task`) to the Redis message broker, passing the path to the uploaded file. It then returns a `task_id` to the frontend.
    *   **UI Polling:** The frontend JavaScript continuously polls a `/check-upload-status` endpoint on the Flask app, providing the `task_id` (stored in the user's session) to get real-time progress updates.
    *   **Product Actions:** When a user creates, edits, or deletes a product, the Flask app performs the necessary operation via the `ProductRepository`.
    *   **Webhook Management:** Webhook configurations are managed directly through Flask routes and the `WebhookRepository`.

2.  **Background Processing (Celery Worker):**
    *   **Task Consumption:** The Celery worker continuously monitors the Redis message broker for new tasks.
    *   **CSV Import:** When an `import_products_task` is received, the worker reads the CSV file (from the shared `uploads` directory) in chunks, processing each chunk to upsert products into the PostgreSQL database via the `ProductRepository`. It reports progress back to Redis.
    *   **Webhook Dispatch:** When `send_webhook_event_task` or `test_webhook_task` is received, the worker retrieves the webhook details from the `WebhookRepository`, sends an HTTP POST request to the target URL, and updates the webhook's `last_triggered` status.

3.  **Data Persistence (PostgreSQL Database):**
    *   The PostgreSQL database stores all product data (`Product` model) and webhook configurations (`Webhook` model). All database interactions are encapsulated within the `ProductRepository` and `WebhookRepository`.

4.  **Message Broker & Cache (Redis):**
    *   Redis acts as the central communication hub for Celery, storing task queues, results, and progress updates.

5.  **Event Notifications (Webhooks):**
    *   Application events (product creation, update, deletion, bulk deletion, CSV import completion) trigger asynchronous `send_webhook_event_task` calls.
    *   The Celery worker dispatches HTTP POST requests to configured webhook URLs, notifying external systems of these events.

## Local Development Setup with Docker Compose

To get the entire application stack running quickly and easily on your local machine, we use Docker Compose.

### Prerequisites

*   **Git:** Version control.
*   **Docker Desktop:** Ensure Docker Desktop is installed and running on your system. This includes Docker Engine and Docker Compose.

### 1. Clone the Repository

Open your terminal and clone your project:

```bash
git clone <repository_url>
cd ACME\ inc # Navigate into your project directory
```

### 2. Configure Environment Variables (Optional for local testing with Docker Compose)

The `docker-compose.yml` file already sets default environment variables suitable for local Docker Compose development (`db` and `redis` service names are used in URLs, `SECRET_KEY` is set).

If you need to override these for specific local testing, you can create a `.env` file in the root directory of the project, based on `.env.example`, but **Docker Compose generally handles this for you internally for inter-service communication.**

### 3. Run the Application Stack

From your project's root directory, execute the following command:

```bash
docker compose up --build
```

*   **`--build`**: This flag ensures your Docker images are built (or rebuilt if changes are detected) from your `Dockerfile` and `Dockerfile.celery`.
*   This command will:
    *   Build Docker images for your Flask app and Celery worker.
    *   Start a PostgreSQL database container.
    *   Start a Redis container.
    *   Start your Flask web application container (which will wait for PostgreSQL and then run `flask init-db` automatically).
    *   Start your Celery worker container.

### 4. Access the Application

Once all services are up and running (monitor your terminal logs; this might take a few minutes on the first run as images are downloaded and dependencies installed):

*   Open your web browser and navigate to: **`http://localhost:5000/`**

### 5. Cleaning Up (Stopping and Removing Containers)

When you are done testing, you can stop and remove all the containers, networks, and volumes created by Docker Compose:

```bash
docker compose down
```

### Testing Webhooks

To test the webhook functionality locally:

1.  Go to `https://webhook.site/` to get a unique test URL.
2.  In your application (accessed at `http://localhost:5000/`), navigate to the "Webhooks" tab.
3.  Click "Add New Webhook" and paste your unique URL.
4.  Select an "Event Type" (e.g., `product_updated`, `product_deleted`, `bulk_products_deleted`, `csv_import_complete`).
5.  Perform the corresponding action in the app (e.g., edit a product, delete a product, bulk delete, upload CSV).
6.  Check webhook.site for incoming requests.

---