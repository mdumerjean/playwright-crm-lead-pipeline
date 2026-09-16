from src.extraction.parsers import (
    clean_text,
    parse_availability,
    parse_category_from_breadcrumb,
    parse_price,
    parse_rating,
)


def test_parse_price_gbp():
    assert parse_price("£45.17") == (45.17, "GBP")


def test_parse_price_with_whitespace():
    assert parse_price("  £51.77 ") == (51.77, "GBP")


def test_parse_price_missing():
    assert parse_price(None) == (None, None)


def test_parse_price_unparsable():
    amount, currency = parse_price("£")
    assert amount is None


def test_parse_availability_in_stock_with_qty():
    assert parse_availability("In stock (19 available)") == (True, 19)


def test_parse_availability_in_stock_no_qty():
    assert parse_availability(" In stock ") == (True, None)


def test_parse_availability_out_of_stock():
    assert parse_availability("Out of stock") == (False, None)


def test_parse_availability_missing():
    assert parse_availability(None) == (False, None)


def test_parse_rating_known_word():
    assert parse_rating("Three") == 3
    assert parse_rating(" five ") == 5


def test_parse_rating_unknown_word():
    assert parse_rating("Zero") is None


def test_parse_category_from_breadcrumb():
    assert parse_category_from_breadcrumb("Home > Books > Travel > It's Only the Himalayas") == "Travel"


def test_parse_category_from_breadcrumb_too_short():
    assert parse_category_from_breadcrumb("Home > Books") is None


def test_clean_text_collapses_whitespace():
    assert clean_text("  It's\n\n  Only   the Himalayas  ") == "It's Only the Himalayas"


def test_clean_text_none():
    assert clean_text(None) == ""
