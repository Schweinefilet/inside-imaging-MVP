"""AWS Lambda handler for Inside Imaging Flask app using Mangum."""

from mangum import Mangum
from app import app

# Wrap the Flask app with Mangum to make it compatible with AWS Lambda
handler = Mangum(app, lifespan="off")
