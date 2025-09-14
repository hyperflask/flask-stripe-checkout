# Flask-Stripe-Checkout

Flask integration of [Stripe Checkout](https://stripe.com/payments/checkout).

Stripe Checkout allows you to quickly handle payments with minimal development.
This Flask extension allows you to build a cart and launch Checkout sessions in less than 10 lines of code.

Check out the example folder for a full example.

## Installation & setup

Install:

    $ pip install flask-stripe-checkout

Setup:

```python
from flask import Flask
from flask_stripe_checkout import StripeCheckout

app = Flask(__name__)
StripeCheckout(app)
```

## Setting up your Stripe account

1. Create a Stripe account
2. Retrieve your API key
3. Register your webhook (`https://yourdomain/stripe-webhook`) and retrieve your endpoint secret

To use webhooks locally:

1. Download [stripe-cli](https://stripe.com/docs/stripe-cli)
2. Login with `stripe login`
3. Run `stripe listen --forward-to localhost:5000/stripe-webhook`

Configure your app before initializing StripeCheckout:

```python
app.config.update({
    "STRIPE_API_KEY": "sk_...",
    "STRIPE_WEBHOOKS_ENDPOINT_SECRET": "whsec_..."
})
```

## Usage

### Introduction

Flask-Stripe-Checkout provides a `current_cart` object that allows you to add Stripe's "line items" to it.
Once your cart is ready, a Checkout session can be started. The cart is stored in the session.

Add an endpoint to add items to your cart:

```python
from flask_stripe_checkout import current_cart

@app.post('/add-to-cart')
def add_to_cart():
    product = Product.get(request.values["product_id"]) # your custom logic to find products
    current_cart.add(product.name, product.amount)
```

Once ready, redirect to checkout:

```python
@app.post('/checkout')
def checkout():
    return current_cart.checkout()
```

!!! note
    When no `success_url` argument is provided to the checkout function, the built-in success page is used

Check out the [API](#API) section for all available `current_cart` methods.

To process the order on successful payment, either:

 - listen to the Stripe webhook event *checkout.session.completed*:
 - when using the built-in success page, listen to the special internal event *checkout.session.success* that triggers when the page is visited

```python
from flask_stripe_checkout import webhook

@webhook.checkout_session_completed()
def checkout_completed(event, session):
    # process order
```

### Using the cart blueprint

The cart blueprint is registered by default and provides endpoints to manage the cart.

When requested normally, the `cart/cart.html` template is returned (feel free to override it).
When requested with `application/json`, an array of line items is returned.

This makes it very easy to use with [htmx](https://htmx.org/) or the standard js `fetch()` function.

Endpoints may be accessible through 2 different URLs:

- a REST compatible one
- another one usable directly using html forms (only using POST)

For cart pages, you can edit the layout of the pages by overriding the `cart/layout.html` template.
A `cart_content` block must be used.

#### cart.view

Show the cart content

    GET /cart

#### cart.update_item

Update an item's quantity

    PUT /cart/<item_idx>
    POST /cart/<item_idx>/update

Where `item_idx` is the item index in the cart.
Provide the `quantity` parameter (via query string or form values).

#### cart.remove_item

Remove an item from the cart

    DELETE /cart/<item_idx>
    POST /cart/<item_idx>/remove

Where `item_idx` is the item index in the cart.

#### cart.clear

Empty the cart

    DELETE /cart
    POST /cart/clear

#### cart.checkout

Redirect to the Stripe Checkout page

    POST /cart/checkout

### Webhooks

When received, signals will be sent. Connect to these signal using `webhook()`:

```python
from flask_stripe_checkout import webhook

@webhook("charge.succeeded")
def charge_succeeded(event):
    # process event
```

You can also quickly retrieve a stripe object:

```python
@webhook("charge.succeeded", retrieve=stripe.Charge)
def charge_succeeded(event, charge):
    # process charge
```

### Subscriptions

To facilitate selling subscriptions, a few helper functions exists.

Create a subscription:

```py
from flask_stripe_checkout.subscription import subscription_checkout

@app.post('/subscribe')
def subscribe():
    return subscription_checkout("subscription_price_id")
```

Listen for the *checkout.session.completed* webhook event to fulfill the subscription:

```python
from flask_stripe_checkout import webhook

@webhook.checkout_session_completed()
def checkout_completed(event, session):
    customer_id = session["customer"]["id"]
    # store customer_id for identitying the current user's subscription
```

Use `redirect_to_customer_portal(customer_id)` to redirect to the customer portal on stripe where the user can manage its subscription.

## Configuration

Available configuration options:

| Config key | Extension argument | Description | Default |
| --- | --- | --- | --- |
| STRIPE_API_KEY | | set `stripe.api_key` | |
| STRIPE_CHECKOUT_CURRENCY | currency | default currency to use when adding items using amounts | USD |
| STRIPE_CHECKOUT_SESSION_OPTIONS | session_options | a dict of options to use for the checkout session. See [checkout api doc](https://stripe.com/docs/api/checkout/sessions/create) | {} |
| STRIPE_CHECKOUT_SUCCESS_REDIRECT | checkout_success_redirect | url to redirect when checkout is successful | |
| STRIPE_WEBHOOKS_ENDPOINT | webhook_endpoint | the stripe webhook endpoint url (use `None` to disable) | /stripe-webhooks |
| STRIPE_WEBHOOKS_ENDPOINT_SECRET | webhook_endpoint_secret | your Stripe webhook endpoint secret to validate incoming hooks | app.secret_key |
| STRIPE_REGISTER_CART_BLUEPRINT | register_cart_blueprint | whether to register the cart blueprint | True |

## API

The `current_cart` object is a session-backed `Cart` instance.

### flask_stripe_checkout.cart.Cart

| Attribute | Description |
| --- | --- |
| `Cart.add()` | add a new `CartItem`. See `CartItem` constructor for available parameters |
| `Cart.update(idx, quantity)` | update the quantity for item at index |
| `Cart.remove(idx)` | remove item at index |
| `Cart.clear()` | empty the cart |
| `Cart.line_items` | the list of items |
| `Cart.total` | total cart amount in cents |
| `Cart.formatted_total` | totgal cart amount formatted using `format_amount()` |
| `Cart.create_checkout_session(**session_options)` | create the stripe.checkout.Session object |
| `Cart.checkout(**session_options)` | create the checkout session and returns a redirect response to the checkout url |

### flask_stripe_checkout.cart.CartItem

`CartItem` is a dict representing a Stripe line item object.

Add an item using a [`Price`](https://stripe.com/docs/api/prices):

```python
current_cart.add(price=price_id, quantity=1)
```

Add an item using a [`Product`](https://stripe.com/docs/api/products) and a custom amount:

```python
current_cart.add(product=product_id, amount=amount, quantity=1, currency=None)
```

Add a product on the fly:

```python
current_cart.add(product_name, amount, quantity=1, currency=None)
```

`currency` defaults to the one provided using `STRIPE_CHECKOUT_CURRENCY`.
You can provide any other line items options.

Special properties on `CartItem` objects:

| Attribute | Description |
| --- | --- |
| `CartItem.price` | retrieve the `Price` object associated to the line item or None |
| `CartItem.product` | retrieve the `Product` object associated to the line item or None |
| `CartItem.description` | retrieve the product description when associated to a product or the product name from price_data |
| `CartItem.currency` | either from the price or from the line item directly |
| `CartItem.quantity` |
| `CartItem.unit_amount` | either from the price or from the line item directly |
| `CartItem.formatted_unit_amount` | the unit_amount formatted using `format_amount()` |
| `CartItem.amount` | the unit_amount multiplied by the quantity |
| `CartItem.formatted_amount` | the amount formatted using `format_amount()` |

### flask_stripe_checkout.cart.format_amount

Format an amount with the currency sign.

```python
format_amount(amount, currency)
```

Available as a filter in templates:

    {{ amount|format_amount(currency) }}

A limited number of currencies are supported. Add support for your own currency:

```python
from flask_stripe_checkout import CURRENCIES
CURRENCIES["USD"] = lambda amount: f"US${amount:,.2f}"
```