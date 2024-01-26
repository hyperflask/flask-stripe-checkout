from .cart import current_cart, CURRENCIES, format_amount
from .cart_blueprint import cart_blueprint
from .webhooks import webhook, webhook_event_from_request, dispatch_webhook_event_as_signal
import stripe
import typing as t
from dataclasses import dataclass


@dataclass
class StripeCheckoutState:
    currency: str
    checkout_session_options: t.Mapping[str, t.Any]
    checkout_success_redirect: t.Optional[str]
    webhooks_endpoint: t.Optional[str]
    webhooks_endpoint_secret: str
    register_cart_blueprint: bool


class StripeCheckout:
    def __init__(self, app=None, **kwargs):
        if app:
            self.init_app(app, **kwargs)

    def init_app(self, app, register_cart_blueprint=True, currency="USD", session_options=None, checkout_success_redirect=None,
                 webhooks_endpoint="/stripe-webhooks", webhooks_endpoint_secret=None):
        if "STRIPE_API_KEY" in app.config:
            stripe.api_key = app.config["STRIPE_API_KEY"]

        state = app.extensions["flask_stripe_checkout"] = StripeCheckoutState(
            currency=app.config.get("STRIPE_CHECKOUT_CURRENCY", currency),
            checkout_session_options=app.config.get("STRIPE_CHECKOUT_SESSION_OPTIONS", session_options) or {},
            checkout_success_redirect=app.config.get("STRIPE_CHECKOUT_SUCCESS_REDIRECT", checkout_success_redirect),
            webhooks_endpoint=app.config.get("STRIPE_WEBHOOKS_ENDPOINT", webhooks_endpoint),
            webhooks_endpoint_secret=app.config.get("STRIPE_WEBHOOKS_ENDPOINT_SECRET", webhooks_endpoint_secret) or app.secret_key,
            register_cart_blueprint=app.config.get("STRIPE_REGISTER_CART_BLUEPRINT", register_cart_blueprint),
        )

        if state.register_cart_blueprint:
            app.register_blueprint(cart_blueprint, url_prefix="/cart")

        if state.webhooks_endpoint:
            @app.post(state.webhooks_endpoint)
            def stripe_webhooks():
                event = webhook_event_from_request()
                dispatch_webhook_event_as_signal(event)
                return "ok"

        app.jinja_env.globals.update(current_cart=current_cart)
        app.jinja_env.filters["format_amount"] = format_amount