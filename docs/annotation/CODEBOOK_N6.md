# Codebook for the failure taxonomy, version 1

This is the second of the two tasks. Do it only after the item annotation is
finished and sent back. It is twenty-six rows and takes about two hours.

Read this once before you start. If a row is not covered by anything here, mark
`unsure` and say why in the note. Do not guess, and do not ask the first author
what the right answer is.

---

## What you are doing

Twenty-six repositories were cloned and built successfully, and then an attempt
was made to re-run the experiment and reproduce a number the paper reports.
Every one of those attempts failed. Each row gives you the reason the harness
recorded.

Your job is to place each failure on two axes:

> **Locus.** Whose problem is it?
>
> **Remedy.** Who, if anyone, could remove it?

You are not being asked whether the failure was reasonable, or whether the
authors were careless. You are being asked where the obstacle sits.

---

## Axis 1: locus

### `artifact`

The obstacle is in what the authors released. A different release would have
removed it. The experiment is reproducible in principle; the published artifact
does not support it.

This covers things the authors control: the commands needed to run the
experiment, whether the repository corresponds to the paper at all, whether a
download the code depends on still resolves, whether the data can be obtained
without a personal application.

### `claim`

The number the paper reports cannot be re-measured by anyone, and no change to
the artifact would help. The measurement depends on hardware nobody else has, on
an external device or service, or on a live production system. It also covers
the case where the paper states no number that could be checked.

The test: could the authors have published something that would make this
reproducible? If no, it is `claim`.

### `harness`

The obstacle is ours. Our environment was missing something it should have had,
or our tooling failed for a reason that says nothing about the study. This is
measurement error on our side and it must be labelled as such rather than
quietly counted as an artifact failure.

### `scope`

The study falls outside the operating envelope we declared. It is too large for
the hardware we said we would use, for example. The artifact is not at fault and
our harness is not broken; we stated in advance that we would not attempt work
of this kind.

### Where the boundaries sit

**`artifact` against `claim`.** Ask whether a different release by the authors
could have made the experiment reproducible. If yes, `artifact`. If no matter
what they published it would still be unreproducible, `claim`.

**`harness` against `scope`.** Ask whether we could have fixed it by improving
our harness *within* the envelope we declared. If yes, `harness`. If the study
is simply bigger or stranger than what we said we would attempt, `scope`.

**`harness` against `artifact`.** Ask who should have supplied the missing
piece. If the authors should have declared it, `artifact`. If our environment
should have had it regardless of what the authors did, `harness`.

---

## Axis 2: remedy

Pick exactly one.

### `author-fix`

The authors could remove the obstacle by changing what they publish.

### `extraction-research`

Better automated extraction could work around the obstacle without the authors
doing anything. Use this when the information needed is present somewhere in the
artifact but was not found or not usable in the form it was found.

### `harness-fix`

We could remove the obstacle by improving our own tooling or environment.

### `intrinsic`

Nobody can remove it. The obstacle is in the nature of the claim or the scale of
the work.

The remedy usually follows from the locus, but not always. When it does not,
choose the remedy you think is right and say why in the note. Those are the rows
we most want to hear about.

---

## The third field

Each row shows you the reason our harness recorded. Tick **the recorded reason
does not match what I can see** when the repository or the paper contradicts it,
for example when the reason says there is no run command and you find one in the
README. Then say what you found in the note.

This is a real check on us, not a formality. Ticking it is useful even when you
are not certain, as long as the note explains.

---

## Where to look

1. The recorded reason, which is the starting point rather than the answer.
2. The repository README, and whether its instructions can actually be followed.
3. The paper's experimental setup, for what hardware or data the number needs.
4. The repository itself, for whether it corresponds to the paper at all.

Five minutes a row is enough. Twenty-six rows, about two hours.

---

## Pace and independence

Work in one or two sessions. Do not revise earlier rows after your understanding
improves; leave them and mention it in the note, because drift between early and
late rows is something we want to see.

Do not open any file in the project that assigns these categories. The
categories you produce are only useful if they were produced independently.
