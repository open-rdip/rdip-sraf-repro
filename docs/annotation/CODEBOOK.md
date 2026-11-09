# Codebook, version 1

Read this once before you start. Come back to it whenever a row is unclear. If
you hit something this document does not cover, mark the row `U`, write what the
problem was in the note column, and keep going. Do not guess, and do not ask the
first author what the right answer is, because that defeats the purpose.

---

## The one question you are answering

For every row in `annotate.csv`:

> Is this item actually supported by this paper or by its repository?

Mark the `decision` column:

| mark | meaning |
|---|---|
| `K` | keep. The item is supported by the paper or the repository. |
| `D` | discard. Not supported, or the value is wrong, or it belongs to other work. |
| `U` | unsure. You looked and genuinely cannot tell. |

**Either source counts.** If the paper does not mention a dependency but
`requirements.txt` declares it, that is `K`. If the repository is silent but the
paper states it, that is `K`.

**Judge support, not importance.** A detail can be trivial and still be `K`. It
is not your job to decide whether the item matters.

**`U` is a real answer.** It is more useful than a guess. Many `U` marks on one
field tells us the definition needs work, which is what this round is for.

Do not open any ground-truth or gold-standard file you come across. The list you
are given is deliberately mixed from several sources so you cannot tell which
items came from where.

---

## Field by field

### dependencies

Software the work needs in order to run.

**Keep** a library, framework or tool that the code imports, that a dependency
file declares (`requirements.txt`, `environment.yml`, `setup.py`,
`pyproject.toml`, `Dockerfile`), or that the paper names as part of the
implementation.

**Discard** software that appears only as prior work, as a comparison system that
was not run, or in related work. "Unlike TensorFlow-based approaches" is not a
dependency on TensorFlow.

**Discard** rows that name a technique rather than a piece of software. Several
of these were produced by an automatic extractor and are wrong by construction.

**On the version field.** The row shows `[version: X]` or `[version: not stated]`.

- A version is **specified** when it is pinned somewhere concrete: `torch==1.9.0`,
  `numpy>=1.20`, a conda lock entry, a Docker image tag, or an explicit statement
  in the paper such as "we use PyTorch 1.9".
- It is **not specified** when the source says only `torch`, or "latest".
- If the row says `not stated` and you find no version anywhere, the row is still
  `K`. The item is the dependency, and "no version given" is a true fact about it.
- If the row claims a version you cannot find anywhere, mark `D` and put the
  correct version in the note if you know it.

### datasets

Data the work trains or evaluates on.

**Keep** a dataset the paper reports results on, or that the code loads.

**Discard** a dataset mentioned only as context, only in related work, or only as
something the authors say they did not use.

Spelling variants are the same dataset: CIFAR-10 and cifar10 are one item. But
CIFAR-10 and CIFAR-100 are different, and ImageNet-1k and ImageNet-21k are
different.

### hyperparameters

A setting chosen before or during training that controls the procedure.

**Keep** learning rate, batch size, epochs, optimiser, weight decay, dropout,
temperature, beam width, layer count when it was a choice. Sources include the
experimental setup section, a config file, a shell script, or a default in an
argument parser.

**Discard** anything that is an output rather than a setting. Accuracy is not a
hyperparameter. Model size is not one when it is a property of a pretrained
checkpoint the authors did not choose.

**The value matters.** The row reads `name = value`. Right name with wrong value
is `D`, and please write the correct value in the note. If the value shows
`not stated`, treat it like an unstated version above: still `K` if the
hyperparameter itself is real. A range is a valid value.

### random_seeds

A seed value actually set in the work.

**Keep** a concrete seed in the code (`torch.manual_seed(42)`,
`np.random.seed(0)`, `--seed 1234`) or in the paper.

**Discard** a seed you cannot find, and a seed that is only an untraceable
library default.

**Be strict here.** One extractor claimed seeds in fifty-two of ninety-five
studies where another claimed nine, so this field is where fabrication shows up.
If you cannot find the exact number, it is `D`, not `U`.

### evaluation_results

A number this paper reports as a result of its own experiments.

**Keep** a metric and value the authors obtained themselves, including ablations
and their own reruns of baselines.

**Discard** a number copied from another paper for comparison. This is the most
common error in this field. A number with a citation marker beside it in a
results table belongs to the cited paper, not this one.

**Discard** a metric name with no value, or a value that does not match the paper.

If the metric and value are right but the bracketed split or dataset is wrong,
mark `K` and note the correction. Do not discard a correct result over a label.

### environment

Facts about the machine: operating system, GPU model, CUDA version, RAM, device
count.

**Keep** anything concrete, such as `gpu: NVIDIA A100` or `cuda: 11.3`.

**Discard** vague statements carrying no information, such as `gpu: modern GPUs`.

### methods

Named techniques this work uses or contributes.

**Keep** the paper's own contributed method, and any named method the authors
actually implemented or ran.

**Discard** methods appearing only in related work, only as background, or only
as a citation. This field has the loosest boundary, so when a method is named but
you cannot tell whether the authors ran it, use `U`.

---

## Where to look, in order

1. The paper's experimental setup or implementation section, and the appendix.
2. The repository `README`.
3. Dependency files: `requirements.txt`, `environment.yml`, `setup.py`, `Dockerfile`.
4. Config files: `configs/`, `*.yaml`, `*.json`.
5. Entry points and their argument parsers: `train.py`, `main.py`, `run.sh`.

Five minutes of searching is enough. If you have not found it by then, it is `U`,
or `D` for seeds.

---

## Adding what the list missed

Put real items no row covers into `additions.csv`: the field name, the item
written the way the rows are written, and where you found it. Add what a careful
reader would expect to be there, not every detail you can think of.

---

## Pace

Twenty to thirty minutes per study. Do not spend an hour on one. Rows you cannot
resolve quickly are `U`. Work in sessions of about an hour, because this gets
tiring and tired annotation is noisy annotation.
