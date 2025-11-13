from flask_sqlalchemy import SQLAlchemy
from celery import Celery

db = SQLAlchemy()

def make_celery(app):
    celery = Celery(
        app.import_name
    )
    celery.conf.update({
        "broker_url": app.config["CELERY_BROKER_URL"],
        "result_backend": app.config["CELERY_RESULT_BACKEND"],
        "include": ["tasks"]
    })

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
