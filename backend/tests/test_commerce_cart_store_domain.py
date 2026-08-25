from commerce.cart_store import sanitize_cart_payload


def test_sanitize_cart_payload_keeps_only_positive_integer_lines():
    assert sanitize_cart_payload(
        {
            "1": {"qty": 2},
            2: {"qty": "3"},
            "0": {"qty": 9},
            "-5": {"qty": 1},
            "bad": {"qty": 4},
            "6": {"qty": 0},
            "7": None,
        }
    ) == {
        "1": {"qty": 2},
        "2": {"qty": 3},
    }


def test_sanitize_cart_payload_rejects_non_mapping_payloads():
    assert sanitize_cart_payload(None) == {}
    assert sanitize_cart_payload([]) == {}
