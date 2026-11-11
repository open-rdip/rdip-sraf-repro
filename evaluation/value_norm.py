"""Value normalisation for extraction matching.

Matching extracted items against a reference failed for reasons that had
nothing to do with extraction quality. Measured over 107 studies and eight
extractors, models agreed with each other 3.7x more than any of them agreed
with the reference, and the gap was largest exactly where an item's identity
is a compound of name and value:

    field                model<->model   model<->reference
    datasets                     0.504               0.238
    methods                      0.302               0.060
    hyperparameters              0.152               0.028
    environment                  0.540               0.033

`learning_rate = 1e-4` and `learning_rate = 0.0001` are one fact. So are
`gpu: NVIDIA P100` and `gpu: Tesla P100-PCIE-16GB`. String identity says they
are four.

The rule followed here is **conservative and symmetric**: collapse only what is
unambiguously the same quantity, and never use a rule that depends on which
side produced the value. Over-normalisation manufactures agreement, which on
this corpus would be a worse error than the one it fixes, because the headline
claim is about whether models and a reference agree.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- numbers
_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def norm_number(raw: str) -> str | None:
    """Canonical form of a numeric literal, or None if it is not one.

    1e-4, 0.0001, 1E-04 and .0001 all become the same string; 16 and 16.0 do
    too. Returns None for anything non-numeric so callers can fall back to
    text handling rather than silently mangling it.
    """
    s = (raw or "").strip().rstrip("%").replace(",", "")
    if not _NUM_RE.match(s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f"{v:.10g}"


# ---------------------------------------------------------------- hardware
#: Accelerator model tokens. Matched as whole tokens so that "a100" does not
#: fire inside an unrelated string. Order matters only for readability.
_GPU_PATTERNS = [
    r"\b([ahvpk])\s?(100|40|80)\b",          # A100 H100 V100 P100 K80 A40
    r"\brtx\s?(\d{3,4})\s?(ti|super)?\b",
    r"\bgtx\s?(\d{3,4})\s?(ti)?\b",
    r"\btitan\s?(x|v|rtx)?\b",
    r"\b(t4|l4|l40s?|a6000|a5000|a10g?|h200|b200|mi\d{3}x?)\b",
    r"\b(\d{4})\s?ti\b",                      # 2080 Ti, 3090 Ti
]


def norm_gpu(raw: str) -> str | None:
    """Reduce a GPU string to its model token, e.g. 'p100', 'rtx3090'.

    'NVIDIA P100', 'Tesla P100-PCIE-16GB' and 'P100' all reduce to 'p100'.
    Vendor names, board variants and memory sizes are dropped because they
    describe the same accelerator and the two schemas spell them differently.
    Returns None when no known model token is present, so unrecognised strings
    fall through to plain text comparison rather than being forced together.
    """
    s = (raw or "").lower()
    for pat in _GPU_PATTERNS:
        m = re.search(pat, s)
        if m:
            return "".join(g for g in m.groups() if g).replace(" ", "") \
                   if m.groups() and any(m.groups()) else m.group(0).replace(" ", "")
    return None


_OS_FAMILIES = ("ubuntu", "debian", "centos", "rhel", "fedora", "macos",
                "darwin", "windows", "linux")


def norm_os(raw: str) -> str | None:
    """OS family plus version when stated, e.g. 'ubuntu20.04', 'ubuntu'.

    Deliberately does NOT collapse 'Ubuntu 22.04' into 'Ubuntu'. They are
    different claims and treating them as equal would invent agreement. The
    bare family is kept as its own value so a reference that says only
    'Ubuntu' stays distinct from one that pins a version.
    """
    s = (raw or "").strip().lower()
    for fam in _OS_FAMILIES:
        if fam in s:
            m = re.search(r"(\d+(?:\.\d+)*)", s)
            return f"{fam}{m.group(1)}" if m else fam
    return None


# ------------------------------------------------------- parameter names
#: Only unambiguous synonyms. "lr" always means learning rate in this corpus;
#: "n" or "size" could mean many things and are deliberately absent.
_PARAM_ALIASES = {
    "lr": "learningrate", "learning_rate": "learningrate",
    "learning rate": "learningrate", "base_lr": "learningrate",
    "batch_size": "batchsize", "batch size": "batchsize", "bs": "batchsize",
    "train_batch_size": "batchsize",
    "num_epochs": "epochs", "n_epochs": "epochs", "epoch": "epochs",
    "max_epochs": "epochs", "num_train_epochs": "epochs",
    "weight_decay": "weightdecay", "wd": "weightdecay",
    "dropout_rate": "dropout", "drop_rate": "dropout",
    "optimiser": "optimizer", "opt": "optimizer",
    "momentum": "momentum", "warmup_steps": "warmupsteps",
    "hidden_size": "hiddensize", "hidden_dim": "hiddensize",
    "embedding_dim": "embeddingdim", "emb_dim": "embeddingdim",
}


def norm_param_name(raw: str) -> str:
    s = re.sub(r"[\s_\-]+", " ", (raw or "").strip().lower())
    if s in _PARAM_ALIASES:
        return _PARAM_ALIASES[s]
    key = s.replace(" ", "_")
    if key in _PARAM_ALIASES:
        return _PARAM_ALIASES[key]
    return s.replace(" ", "")


# --------------------------------------------------------------- top level
def norm_value(raw: str, hint: str = "") -> str:
    """Normalise a value string. `hint` is the key it was stated under."""
    s = (raw or "").strip()
    if not s:
        return ""
    n = norm_number(s)
    if n is not None:
        return n
    h = (hint or "").lower()
    if "gpu" in h or "cuda" in h or "device" in h:
        g = norm_gpu(s)
        if g:
            return g
    if "os" in h:
        o = norm_os(s)
        if o:
            return o
    g = norm_gpu(s)
    if g and not h:
        return g
    return re.sub(r"[\s_\-]+", "", s.lower())


# ------------------------------------------------- unicode in metric names
#: ML metric names mix Greek letters and sub/superscripts with their spelled
#: forms: a model writes "Sα" where the reference writes "S_alpha", and
#: "F₁" where the reference writes "F1". The scorer's `_norm` strips
#: non-ASCII, so "Sα" collapsed to "s" and could never match "s alpha".
#: Measured on study003 the values agreed exactly (77.0, 81.1) and only the
#: name differed, so this alone was producing F1 = 0.000 on the field.
_GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "ζ": "zeta", "η": "eta", "θ": "theta", "ι": "iota", "κ": "kappa",
    "λ": "lambda", "μ": "mu", "ν": "nu", "ξ": "xi", "π": "pi", "ρ": "rho",
    "σ": "sigma", "ς": "sigma", "τ": "tau", "υ": "upsilon", "φ": "phi",
    "χ": "chi", "ψ": "psi", "ω": "omega",
    "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta", "Θ": "theta",
    "Λ": "lambda", "Μ": "mu", "Π": "pi", "Σ": "sigma", "Φ": "phi",
    "Χ": "chi", "Ψ": "psi", "Ω": "omega",
}
_SUBSUP = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5",
    "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
    "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}


def translit(raw: str) -> str:
    """Spell out Greek letters and sub/superscript digits.

    Applied before any punctuation stripping, so that a symbol becomes a word
    rather than disappearing. Deliberately does not touch anything else: this
    is transliteration, not normalisation, and it cannot make two different
    metrics equal.
    """
    s = raw or ""
    for k, v in _GREEK.items():
        s = s.replace(k, v)
    for k, v in _SUBSUP.items():
        s = s.replace(k, v)
    return s
