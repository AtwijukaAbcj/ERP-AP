import base64
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import stripe
from django.conf import settings


logger = logging.getLogger(__name__)


class PaymentProviderError(Exception):
    pass


def create_stripe_checkout(attempt, success_url, cancel_url):
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentProviderError("Stripe online payments are not configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    amount_minor = int(attempt.amount * 100)
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            client_reference_id=str(attempt.pk),
            line_items=[
                {
                    "price_data": {
                        "currency": attempt.currency.lower(),
                        "product_data": {
                            "name": f"School invoice INV{attempt.invoice_id:05d}",
                        },
                        "unit_amount": amount_minor,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "attempt_id": str(attempt.pk),
                "invoice_id": str(attempt.invoice_id),
            },
            success_url=success_url,
            cancel_url=cancel_url,
            idempotency_key=str(attempt.idempotency_key),
        )
    except stripe.error.StripeError as error:
        logger.exception("Stripe checkout session creation failed.")
        raise PaymentProviderError("Stripe could not start the payment.") from error
    if not session.id or not session.url:
        raise PaymentProviderError("Stripe returned an incomplete checkout session.")
    return session


def retrieve_stripe_checkout(session_id):
    if not settings.STRIPE_SECRET_KEY:
        raise PaymentProviderError("Stripe online payments are not configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        return stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as error:
        logger.exception("Stripe checkout session retrieval failed.")
        raise PaymentProviderError("Stripe payment confirmation could not be retrieved.") from error


def _paypal_base_url():
    if settings.PAYPAL_MODE == "live":
        return "https://api-m.paypal.com"
    if settings.PAYPAL_MODE == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    raise PaymentProviderError("PayPal mode must be either sandbox or live.")


def _paypal_access_token():
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        raise PaymentProviderError("PayPal online payments are not configured.")

    credentials = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
    authorization = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    request = Request(
        f"{_paypal_base_url()}/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {authorization}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    response = _paypal_json_request(request)
    access_token = response.get("access_token")
    if not access_token:
        raise PaymentProviderError("PayPal did not return an access token.")
    return access_token


def _paypal_json_request(request):
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise PaymentProviderError("PayPal returned an invalid response.")
            return payload
    except HTTPError as error:
        logger.error("PayPal API request failed with HTTP status %s.", error.code)
        raise PaymentProviderError("PayPal could not process the payment request.") from error
    except (URLError, TimeoutError) as error:
        logger.error("PayPal API request could not reach the provider.")
        raise PaymentProviderError("PayPal is temporarily unavailable.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.error("PayPal returned an invalid response.")
        raise PaymentProviderError("PayPal returned an invalid response.") from error


def _paypal_request(method, path, payload, request_id):
    access_token = _paypal_access_token()
    request = Request(
        f"{_paypal_base_url()}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "PayPal-Request-Id": request_id,
        },
        method=method,
    )
    return _paypal_json_request(request)


def create_paypal_order(attempt, return_url, cancel_url):
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": str(attempt.pk),
                "custom_id": str(attempt.pk),
                "invoice_id": f"INV{attempt.invoice_id:05d}",
                "amount": {
                    "currency_code": attempt.currency,
                    "value": f"{attempt.amount:.2f}",
                },
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
        },
    }
    response = _paypal_request(
        "POST",
        "/v2/checkout/orders",
        payload,
        str(attempt.idempotency_key),
    )
    approval_url = next(
        (
            link["href"]
            for link in response.get("links", [])
            if link.get("rel") == "approve" and link.get("href")
        ),
        None,
    )
    if not response.get("id") or not approval_url:
        raise PaymentProviderError("PayPal returned an incomplete checkout order.")
    return response["id"], approval_url


def capture_paypal_order(order_id, request_id):
    return _paypal_request(
        "POST",
        f"/v2/checkout/orders/{quote(order_id, safe='')}/capture",
        {},
        request_id,
    )
