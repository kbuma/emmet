import datetime
import json
from pathlib import Path

import numpy as np
import pytest
from bson.objectid import ObjectId
from emmet.core.utils import DocEnum, ValueEnum, jsanitize, get_md5_blocked
from monty.json import MSONable
from monty.serialization import dumpfn


def test_jsanitize():
    """
    Tests emmet Jsanitize which converts MSONable classes into dicts
    """
    # clean_json should have no effect on None types.
    d = {"hello": 1, "world": None}
    clean = jsanitize(d)
    assert clean["world"] is None
    assert json.loads(json.dumps(d)) == json.loads(json.dumps(clean))

    d = {"hello": GoodMSONClass(1, 2, 3)}
    with pytest.raises(TypeError):
        json.dumps(d)

    clean = jsanitize(d)
    assert isinstance(clean["hello"], dict)
    clean_strict = jsanitize(d, strict=True)
    assert clean_strict["hello"]["a"] == 1
    assert clean_strict["hello"]["b"] == 2

    d = {"dt": datetime.datetime.now()}
    clean = jsanitize(d)
    assert isinstance(clean["dt"], str)
    clean = jsanitize(d, allow_bson=True)
    assert isinstance(clean["dt"], datetime.datetime)

    d = {
        "a": ["b", np.array([1, 2, 3])],
        "b": ObjectId.from_datetime(datetime.datetime.now()),
    }
    clean = jsanitize(d)
    assert clean["a"] == ["b", [1, 2, 3]]
    assert isinstance(clean["b"], str)

    rnd_bin = bytes(np.random.rand(10))
    d = {"a": bytes(rnd_bin)}
    clean = jsanitize(d, allow_bson=True)
    assert clean["a"] == bytes(rnd_bin)
    assert isinstance(clean["a"], bytes)


class GoodMSONClass(MSONable):
    def __init__(self, a, b, c, d=1, **kwargs):
        self.a = a
        self.b = b
        self._c = c
        self._d = d
        self.kwargs = kwargs

    def __eq__(self, other):
        return (
            self.a == other.a
            and self.b == other.b
            and self._c == other._c
            and self._d == other._d
            and self.kwargs == other.kwargs
        )


def test_value_enum(monkeypatch, tmp_path):
    class TempEnum(ValueEnum):
        A = "A"
        B = "B"

    assert str(TempEnum.A) == "A"
    assert str(TempEnum.B) == "B"

    dumpfn(TempEnum, tmp_path / "temp.json")
    assert Path(tmp_path, "temp.json").is_file()


def test_doc_enum():
    class TestEnum(DocEnum):
        A = "A", "Describes A"
        B = "B", "Might describe B"

    assert str(TestEnum.A) == "A"
    assert TestEnum.B.__doc__ == "Might describe B"


def test_blocked_md5(tmp_dir):
    import hashlib
    from monty.io import zopen

    file_text = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
        "sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    ).encode()

    with zopen("test_md5.gz", "wb") as f:
        f.write(file_text)

    assert get_md5_blocked("test_md5.gz") == hashlib.md5(file_text).hexdigest()
