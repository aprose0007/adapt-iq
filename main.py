from firebase_functions import https_fn
from firebase_admin import initialize_app

# The Firebase Admin SDK initialized in database.py happens when app imports it
from app import app as flask_app

@https_fn.on_request(max_instances=1)
def server(req: https_fn.Request) -> https_fn.Response:
    with flask_app.request_context(req.environ):
        return flask_app.full_dispatch_request()
