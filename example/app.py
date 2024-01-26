from flask import Flask, render_template, request, redirect, url_for
from flask_stripe_checkout import StripeCheckout, current_cart, webhook
import random


app = Flask(__name__)
app.config.update({
    "SECRET_KEY": "changeme",
    "STRIPE_API_KEY": "sk_...",
    "STRIPE_WEBHOOKS_ENDPOINT_SECRET": "whsec_..."
})
StripeCheckout(app)


PRODUCTS = [{"title": f"Product n°{i+1}", "amount": random.randint(1, 100)} for i in range(10)]


@app.route("/")
def index():
    return render_template("index.html", products=PRODUCTS)


@app.post("/add-to-cart")
def add_to_cart():
    product = PRODUCTS[int(request.form["product_id"])]
    current_cart.add(product["title"], product["amount"] * 100)
    return redirect(url_for("index"))


@webhook.checkout_session_completed()
def checkout_session_completed(event, session):
    app.logger.info("Checkout completed")