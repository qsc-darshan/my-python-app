import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import add

def test_add():
    result = add(2, 3)
    print(f"add(2, 3) returned {result}")
    assert result == 6

