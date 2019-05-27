import graphene
from tests.api.utils import get_graphql_content
from saleor.checkout.utils import add_voucher_to_checkout
from tests.api.test_checkout import (
    MUTATION_CHECKOUT_LINES_DELETE,
    MUTATION_CHECKOUT_SHIPPING_ADDRESS_UPDATE,
)

MUTATION_CHECKOUT_UPDATE_VOUCHER = """
    mutation($checkoutId: ID!, $voucherCode: String) {
        checkoutUpdateVoucher(
            checkoutId: $checkoutId, voucherCode: $voucherCode) {
            errors {
                field
                message
            }
            checkout {
                id,
                voucherCode
            }
        }
    }
"""


def _mutate_checkout_update_voucher(client, variables):
    response = client.post_graphql(MUTATION_CHECKOUT_UPDATE_VOUCHER, variables)
    content = get_graphql_content(response)
    return content["data"]["checkoutUpdateVoucher"]


def test_checkout_add_voucher(api_client, checkout_with_item, voucher):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "voucherCode": voucher.code}
    data = _mutate_checkout_update_voucher(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] == voucher.code


def test_checkout_remove_voucher(api_client, checkout_with_item):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id}
    data = _mutate_checkout_update_voucher(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] is None
    assert checkout_with_item.voucher_code is None


def test_checkout_add_voucher_invalid_checkout(api_client, voucher):
    variables = {"checkoutId": "XXX", "voucherCode": voucher.code}
    data = _mutate_checkout_update_voucher(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "checkoutId"


def test_checkout_add_voucher_invalid_code(api_client, checkout_with_item):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "voucherCode": "XXX"}
    data = _mutate_checkout_update_voucher(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "voucherCode"


def test_checkout_add_voucher_not_applicable_voucher(
    api_client, checkout_with_item, voucher_with_high_min_amount_spent
):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {
        "checkoutId": checkout_id,
        "voucherCode": voucher_with_high_min_amount_spent.code,
    }
    data = _mutate_checkout_update_voucher(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "voucherCode"


def test_checkout_lines_delete_with_not_applicable_voucher(
    user_api_client, checkout_with_item, voucher
):
    voucher.min_amount_spent = checkout_with_item.get_subtotal().gross
    voucher.save(update_fields=["min_amount_spent"])

    add_voucher_to_checkout(voucher, checkout_with_item)
    assert checkout_with_item.voucher_code == voucher.code

    line = checkout_with_item.lines.first()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    line_id = graphene.Node.to_global_id("CheckoutLine", line.pk)
    variables = {"checkoutId": checkout_id, "lineId": line_id}
    response = user_api_client.post_graphql(MUTATION_CHECKOUT_LINES_DELETE, variables)
    content = get_graphql_content(response)

    data = content["data"]["checkoutLineDelete"]
    assert not data["errors"]
    checkout_with_item.refresh_from_db()
    assert checkout_with_item.lines.count() == 0
    assert checkout_with_item.voucher_code is None


def test_checkout_shipping_address_update_with_not_applicable_voucher(
    user_api_client,
    checkout_with_item,
    voucher_shipping_type,
    graphql_address_data,
    address_other_country,
    shipping_method,
):
    assert checkout_with_item.shipping_address is None
    assert checkout_with_item.voucher_code is None

    checkout_with_item.shipping_address = address_other_country
    checkout_with_item.shipping_method = shipping_method
    checkout_with_item.save(update_fields=["shipping_address", "shipping_method"])
    assert checkout_with_item.shipping_address.country == address_other_country.country

    voucher = voucher_shipping_type
    assert voucher.countries[0].code == address_other_country.country

    add_voucher_to_checkout(voucher, checkout_with_item)
    assert checkout_with_item.voucher_code == voucher.code

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    new_address = graphql_address_data
    variables = {"checkoutId": checkout_id, "shippingAddress": new_address}
    response = user_api_client.post_graphql(
        MUTATION_CHECKOUT_SHIPPING_ADDRESS_UPDATE, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkoutShippingAddressUpdate"]
    assert not data["errors"]

    checkout_with_item.refresh_from_db()
    checkout_with_item.shipping_address.refresh_from_db()

    assert checkout_with_item.shipping_address.country == new_address["country"]
    assert checkout_with_item.voucher_code is None


QUERY_GET_CHECKOUT_GIFT_CARD_CODES = """
query getCheckout($token: UUID!) {
  checkout(token: $token) {
    token
    giftCards {
      displayCode
      currentBalance {
        amount
      }
    }
  }
}
"""


def test_checkout_get_gift_card_code(user_api_client, checkout_with_gift_card):
    gift_card = checkout_with_gift_card.gift_cards.first()
    variables = {"token": str(checkout_with_gift_card.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"][0]
    assert data["displayCode"] == gift_card.display_code
    assert data["currentBalance"]["amount"] == gift_card.current_balance.amount


def test_checkout_get_gift_card_codes(
    user_api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    checkout_with_gift_card.gift_cards.add(gift_card_created_by_staff)
    checkout_with_gift_card.save()
    gift_card_0 = checkout_with_gift_card.gift_cards.first()
    gift_card_1 = checkout_with_gift_card.gift_cards.last()
    variables = {"token": str(checkout_with_gift_card.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert data[0]["displayCode"] == gift_card_0.display_code
    assert data[0]["currentBalance"]["amount"] == gift_card_0.current_balance.amount
    assert data[1]["displayCode"] == gift_card_1.display_code
    assert data[1]["currentBalance"]["amount"] == gift_card_1.current_balance.amount


def test_checkout_get_gift_card_code_without_gift_card(user_api_client, checkout):
    variables = {"token": str(checkout.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert not data


MUTATION_CHECKOUT_ADD_PROMO_CODE = """
    mutation($checkoutId: ID!, $promoCode: String!) {
        checkoutAddPromoCode(
            checkoutId: $checkoutId, promoCode: $promoCode) {
            errors {
                field
                message
            }
            checkout {
                id,
                voucherCode
                giftCards {
                    code
                }
            }
        }
    }
"""


def _mutate_checkout_add_promo_code(client, variables):
    response = client.post_graphql(MUTATION_CHECKOUT_ADD_PROMO_CODE, variables)
    content = get_graphql_content(response)
    return content["data"]["checkoutAddPromoCode"]


def test_checkout_add_promo_code_voucher(api_client, checkout_with_item, voucher):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] == voucher.code


def test_checkout_add_promo_code_voucher_invalid_checkout(api_client, voucher):
    variables = {"checkoutId": "XXX", "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "checkoutId"


def test_checkout_add_promo_code_voucher_invalid_code(api_client, checkout_with_item):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": "XXX"}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


def test_checkout_add_promo_code_voucher_not_applicable_voucher(
    api_client, checkout_with_item, voucher_with_high_min_amount_spent
):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": voucher_with_high_min_amount_spent.code,
    }
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


MUTATION_CHECKOUT_REMOVE_PROMO_CODE = """
    mutation($checkoutId: ID!, $promoCode: String!) {
        checkoutRemovePromoCode(
            checkoutId: $checkoutId, promoCode: $promoCode) {
            errors {
                field
                message
            }
            checkout {
                id,
                voucherCode
                giftCards {
                    code
                }
            }
        }
    }
"""


def test_checkout_remove_promo_code_voucher(api_client, checkout_with_voucher):
    assert checkout_with_voucher.voucher_code is not None
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_voucher.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": checkout_with_voucher.voucher_code,
    }

    response = api_client.post_graphql(MUTATION_CHECKOUT_REMOVE_PROMO_CODE, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkoutRemovePromoCode"]

    checkout_with_voucher.refresh_from_db()
    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] is None
    assert checkout_with_voucher.voucher_code is None
