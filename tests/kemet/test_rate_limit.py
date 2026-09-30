from flask import Flask
from app.core.rate_limit import _identity_key

def test_rate_limit_identity_binds_ip_and_email():
    app = Flask(__name__)
    with app.test_request_context("/login", method="POST", data={"email": " User@Example.com "}, environ_base={"REMOTE_ADDR": "10.0.0.8"}):
        key = _identity_key()
        assert key == "10.0.0.8:user@example.com"
