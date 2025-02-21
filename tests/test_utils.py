import pytest
from utils import make_tiny

def test_make_tiny():
    long_url = "https://www.example.com"
    short_url = make_tiny(long_url)
    assert short_url.startswith("http://tinyurl.com/")