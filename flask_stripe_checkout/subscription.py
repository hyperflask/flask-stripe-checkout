import stripe
from flask import url_for, redirect
from .cart import Cart


def create_subscription_checkout(price_id, client_reference_id=None, **session_options):
    cart = Cart()
    cart.add(price=price_id, quantity=1)
    return cart.create_checkout_session(mode="subscription", client_reference_id=client_reference_id, **session_options)


def subscription_checkout(price_id, client_reference_id=None, **session_options):
    session = create_subscription_checkout(price_id, client_reference_id, **session_options)
    return redirect(session.url, code=303)


def create_customer_portal_session(customer_id, return_url=None):
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url or url_for("index", _external=True),
    )


def redirect_to_customer_portal(customer_id, return_url=None):
    session = create_customer_portal_session(customer_id, return_url)
    return redirect(session.url, code=303)


def upgrade_subscription(customer_id, price_id, client_reference_id=None, return_url=None, **modify_kwargs):
    subs = stripe.Subscription.list(customer=customer_id)
    if not subs:
        return subscription_checkout(price_id, customer=customer_id, client_reference_id=client_reference_id, next=return_url)
    sub_item_id = subs["data"][0]["items"]["data"][0]["id"]
    stripe.SubscriptionItem.modify(sub_item_id, price=price_id, **modify_kwargs)
    return redirect_to_customer_portal(customer_id, return_url)