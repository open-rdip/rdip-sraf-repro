import pytest
from evaluation.value_norm import (norm_number, norm_gpu, norm_os,
                                   norm_param_name, norm_value)


@pytest.mark.parametrize("a,b", [
    ("1e-4", "0.0001"), ("1E-04", "0.0001"), (".0001", "0.0001"),
    ("16", "16.0"), ("3e8", "300000000"), ("0.05", "5e-2"),
])
def test_numeric_forms_collapse(a, b):
    assert norm_number(a) == norm_number(b) is not None


def test_non_numeric_returns_none_rather_than_mangling():
    for s in ("AdamW", "cosine", "", "1.2.3", "p100"):
        assert norm_number(s) is None


@pytest.mark.parametrize("s", ["NVIDIA P100", "Tesla P100-PCIE-16GB", "p100",
                               "1x NVIDIA Tesla P100"])
def test_gpu_variants_collapse(s):
    assert norm_gpu(s) == norm_gpu("P100")


def test_distinct_gpus_stay_distinct():
    assert norm_gpu("A100") != norm_gpu("P100")
    assert norm_gpu("RTX 3090") != norm_gpu("RTX 2080")


def test_unknown_hardware_returns_none_so_it_falls_through():
    assert norm_gpu("some custom accelerator") is None


def test_os_version_is_not_collapsed_into_family():
    """Ubuntu 22.04 and Ubuntu are different claims; collapsing invents agreement."""
    assert norm_os("Ubuntu 22.04") != norm_os("Ubuntu")
    assert norm_os("Ubuntu 22.04") == norm_os("ubuntu  22.04")


def test_param_aliases_only_where_unambiguous():
    assert norm_param_name("lr") == norm_param_name("learning_rate") \
        == norm_param_name("Learning Rate")
    assert norm_param_name("batch_size") == norm_param_name("bs")
    # distinct parameters must not merge
    assert norm_param_name("weight_decay") != norm_param_name("dropout")


def test_norm_value_routes_by_hint():
    assert norm_value("1e-4") == norm_value("0.0001")
    assert norm_value("Tesla P100-PCIE-16GB", hint="gpu") == norm_value("NVIDIA P100", hint="gpu")
    assert norm_value("Ubuntu 20.04", hint="os") == norm_value("ubuntu 20.04", hint="os")


def test_normalisation_is_symmetric():
    """No rule may depend on which side produced the value."""
    pairs = [("1e-4", "0.0001"), ("NVIDIA P100", "P100"), ("AdamW", "adamw")]
    for a, b in pairs:
        assert norm_value(a) == norm_value(b) == norm_value(b) == norm_value(a)


from evaluation.value_norm import translit


def test_greek_is_spelled_out_not_deleted():
    assert translit("Sα") == "Salpha"
    assert translit("F₁") == "F1"
    assert translit("R²") == "R2"
    assert translit("χ²") == "chi2"


def test_translit_leaves_ascii_untouched():
    assert translit("mIoU") == "mIoU"
    assert translit("Dice score") == "Dice score"


def test_translit_cannot_merge_distinct_metrics():
    assert translit("Sα") != translit("Sβ")
