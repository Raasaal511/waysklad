import pytest

from app.domain.common.exceptions import DomainError
from app.domain.common.phone import Phone


def test_normalizes_national_format_to_e164():
    assert str(Phone("89280001122")) == "+79280001122"


def test_normalizes_number_without_country_code():
    assert str(Phone("9280001122")) == "+79280001122"


def test_accepts_already_normalized_e164():
    assert str(Phone("+79280001122")) == "+79280001122"


def test_different_input_formats_are_equal_after_normalization():
    assert Phone("89280001122") == Phone("+79280001122") == Phone("9280001122")


def test_rejects_garbage_input():
    with pytest.raises(DomainError):
        Phone("не телефон")


def test_rejects_too_short_number():
    with pytest.raises(DomainError):
        Phone("123")
