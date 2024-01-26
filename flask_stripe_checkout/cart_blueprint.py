from flask import request, Blueprint, redirect, render_template, abort, jsonify, current_app
from urllib.parse import urlparse, urljoin
import stripe
from .cart import current_cart
from .webhooks import stripe_signal


cart_blueprint = Blueprint("cart", __name__, template_folder="templates")


@cart_blueprint.get("/")
def view():
    if request.is_json:
        return jsonify(current_cart.line_items)
    return render_template("cart/cart_page.html", cart=current_cart)


def cart_response():
    next = request.values.get("next")
    if next == "204":
        return "", 204
    if next and is_safe_redirect_url(next):
        return redirect(next)
    if request.is_json:
        return jsonify(current_cart.line_items)
    return render_template("cart/cart.html", cart=current_cart)


@cart_blueprint.put("/<int:item_idx>")
@cart_blueprint.post('/<int:item_idx>/update')
def update_item(item_idx):
    try:
        quantity = int(request.values["quantity"])
    except:
        abort(400)
    current_cart.update(item_idx, quantity)
    return cart_response()


@cart_blueprint.delete("/<int:item_idx>")
@cart_blueprint.post('/<int:item_idx>/remove')
def remove_item(item_idx):
    current_cart.remove(item_idx)
    return cart_response()


@cart_blueprint.delete("/")
@cart_blueprint.post('/clear')
def clear():
    current_cart.clear()
    return cart_response()


@cart_blueprint.post("/checkout")
def checkout():
    return current_cart.checkout()


@cart_blueprint.route("/checkout/success")
def checkout_success():
    session_id = request.args["session_id"]
    session = stripe.checkout.Session.retrieve(session_id, expand=['line_items', 'customer', 'subscription'])
    current_cart.clear()
    stripe_signal("checkout.session.success").send(current_app, session=session)

    if "next" in request.args:
        return redirect(request.args["next"])

    if current_app.extensions["flask_stripe_checkout"].checkout_success_redirect:
        return redirect(current_app.extensions["flask_stripe_checkout"].checkout_success_redirect)
    
    out = render_template("cart/checkout_success.html", session=session)
    return out


def is_safe_redirect_url(target):
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return (
        redirect_url.scheme in ("http", "https")
        and host_url.netloc == redirect_url.netloc
    )
