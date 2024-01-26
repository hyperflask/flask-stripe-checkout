from flask import current_app, session, redirect, url_for, g
from werkzeug.local import LocalProxy
from functools import cached_property
import stripe
import urllib.parse


CURRENCIES = {
    "USD": lambda amount: f"US${amount:,.2f}",
    "EUR": lambda amount: f"{amount:,.2f} €",
    "GBP": lambda amount: f"£{amount:,.2f}",
    "AUD": lambda amount: f"A${amount:,.2f}",
    "BRL": lambda amount: f"R${amount:,.2f}",
    "CAD": lambda amount: f"${amount:,.2f}",
    "CNY": lambda amount: f"¥{amount:,.2f}",
    "HKD": lambda amount: f"HK${amount:,.2f}",
    "INR": lambda amount: f"₹{amount:,.2f}",
}


def format_amount(amount_in_cents, currency):
    currency_format = CURRENCIES.get(currency)
    amount = amount_in_cents / 100
    if currency_format:
        return currency_format(amount)
    return f"${amount:,.2f}"


class CartError(Exception):
    pass


class CartItem(dict):
    @classmethod
    def from_dict(cls, line_item):
        item = cls.__new__(cls)
        item.update(line_item)
        return item
    
    def __init__(self, product_name=None, amount=None, quantity=1, currency=None, price=None, product=None, **line_item_options):
        if not price and amount is None:
            raise CartError("One of price or amount must be provided")
        
        line_item = dict(line_item_options, quantity=quantity)
        if price:
            line_item["price"] = price
        else:
            line_item.setdefault("price_data", {}).update({
                "unit_amount": amount,
                "currency": currency or current_app.extensions["flask_stripe_checkout"].currency
            })
            if product:
                line_item["price_data"]["product"] = product
            elif not product_name:
                raise CartError("Missing product name")
            else:
                line_item["price_data"].setdefault("product_data", {})["name"] = product_name

        super().__init__(line_item)
    
    @cached_property
    def price(self):
        if self.get("price"):
            return stripe.Price.retrieve(self.line_item["price"])
        
    @cached_property
    def product(self):
        if self.get("price"):
            product_id = self.price["product"]
        elif self["price_data"].get("product"):
            product_id = self["price_data"]["product"]
        else:
            return
        return stripe.Product.retrieve(product_id)
    
    @property
    def description(self):
        if self.get("price") or self["price_data"].get("product"):
            return self.product["description"]
        return self["price_data"]["product_data"]["name"]
    
    @property
    def currency(self):
        if self.get("price"):
            return self.price["currency"].upper()
        return self["price_data"]["currency"].upper()
    
    @property
    def quantity(self):
        return self["quantity"]
    
    @quantity.setter
    def quantity(self, value):
        self["quantity"] = value

    @property
    def unit_amount(self):
        if self.get("price"):
            return self.price["unit_amount"]
        return self["price_data"]["unit_amount"]
    
    @property
    def formatted_unit_amount(self):
        return format_amount(self.unit_amount, self.currency)

    @property
    def amount(self):
        return self.unit_amount * self["quantity"]
    
    @property
    def formatted_amount(self):
        return format_amount(self.amount, self.currency)


class Cart:
    def __init__(self, line_items=None, session_options=None):
        self.line_items = line_items or []
        self.session_options = session_options or {}

    def add(self, description=None, amount=None, quantity=1, **kwargs):
        self.line_items.append(CartItem(description, amount, quantity, **kwargs))
        self.save()

    def update(self, idx, quantity):
        if len(self.line_items) <= idx:
            raise CartError("Unknown item")
        if quantity <= 0:
            self.line_items.pop(idx)
        else:
            self.line_items[idx].quantity = quantity
        self.save()

    def remove(self, idx):
        if len(self.line_items) <= idx:
            raise CartError("Unknown item")
        self.line_items.pop(idx)
        self.save()

    def clear(self):
        self.line_items = []
        self.session_options = {}
        self.save()

    def save(self):
        pass
    
    @property
    def total(self):
        return sum([i.amount for i in self.line_items])
    
    @property
    def formatted_total(self):
        if self.line_items:
            return format_amount(self.total, self.line_items[0].currency)
        return "0"
    
    def __contains__(self, value):
        for item in self.line_items:
            if value.startswith("prod_") and item.product["id"] == value:
                return True
            if value.startswith("price_") and item["price"] == value:
                return True
            if item.description == value:
                return True
        return False

    def create_checkout_session(self, **session_options):
        options = dict(current_app.extensions["flask_stripe_checkout"].checkout_session_options)
        options.update(self.session_options)
        options.update(session_options)
        options.setdefault("mode", "payment")
        if "success_url" not in options:
            options["success_url"] = url_for("cart.checkout_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}"
            if "next" in options:
                options["success_url"] += "&next=" + urllib.parse.quote_plus(options.pop("next"))
        return stripe.checkout.Session.create(line_items=self.line_items, **options)

    def checkout(self, **session_options):
        checkout_session = self.create_checkout_session(**session_options)
        return redirect(checkout_session.url, code=303)
    

class SessionCart(Cart):
    def __init__(self):
        super().__init__([CartItem.from_dict(d) for d in session.get("cart-items", [])], session.get("cart-options"))

    def save(self):
        session["cart-items"] = self.line_items
        session["cart-options"] = self.session_options

    def clear(self):
        super().clear()
        session.pop("cart-item", None)
        session.pop("cart-options", None)


def get_session_cart():
    if "cart" not in g:
        g.cart = SessionCart()
    return g.cart


current_cart = LocalProxy(get_session_cart)
