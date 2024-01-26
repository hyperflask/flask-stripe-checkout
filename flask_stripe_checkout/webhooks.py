import stripe
from functools import partial
from flask import request, current_app, abort
from flask.signals import Namespace


_signals = Namespace()


def webhook_event_from_request():
    try:
        return stripe.Webhook.construct_event(
            request.get_data(),
            request.headers["Stripe-Signature"],
            current_app.extensions["flask_stripe_checkout"].webhooks_endpoint_secret
        )
    except ValueError:
        abort(400)
    except stripe.error.SignatureVerificationError:
        abort(400)


def stripe_signal(event_name):
    return _signals.signal('stripe-%s' % event_name)


def dispatch_webhook_event_as_signal(event):
    stripe_signal(event["type"]).send(event)


def webhook(event_type, retrieve=None, **retrieve_kwargs):
    def decorator(func):
        def signal_handler(event):
            if retrieve:
                obj = retrieve.retrieve(event['data']['object']['id'], **retrieve_kwargs)
                func(event, obj)
            else:
                func(event)

        stripe_signal(event_type).connect(signal_handler, weak=False)
        return func

    return decorator


webhook.checkout_session_success = lambda: stripe_signal("checkout.session.success").connect
webhook.checkout_session_completed = partial(webhook, "checkout.session.completed", retrieve=stripe.checkout.Session, expand=["line_items", "customer"])
