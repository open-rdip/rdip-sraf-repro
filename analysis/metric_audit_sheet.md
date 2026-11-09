# Metric audit worksheet

Sample of 10 from 49 studies where `repo_facts` detected no computable metric.
Selection is `random.Random(20261231).shuffle` over the sorted list, so it is reproducible and was fixed before any study was looked at.

For each study, set **verdict** to one of:

- `detector_gap` — the repository DOES compute a metric, in a form the four signals miss. Note how it is expressed.
- `genuinely_absent` — no evaluation code. The claim cannot be checked from this artifact at all.
- `unclear` — you could not tell in a couple of minutes. Say so rather than guessing; an honest `unclear` rate is itself reportable.

Candidate lines below are from a deliberately loose keyword search and include false hits by design. They are a starting point, not evidence.

---

## study078

- repo: https://github.com/qqqyang/shuffle-qudio
- commit: `4f1fa4530c431eb9a66ceb6b9fc09907617f6c01`
- paper claims: approximation error, communication overhead, speedup ratio
- code files: 49

Evaluation-shaped filenames: **none**

Candidate lines (loose search, expect false hits):

```
README.md:1: # Shuffle-QUDIO: accelerate distributed VQE with enhanced trainability
README.md:3: This repository is the official implementation of [*Shuffle-QUDIO: accelerate distributed VQE with enhanced trainability
train_pl_torch.py:108: #         mapping='jordan_wigner'
train_pl_torch.py:122: def evaluate(model, feat_test, label_test):
circuit/tutorial_quantum_chemistry_pl.py:22: Accurate molecular properties can be computed from the wave function describing the
circuit/tutorial_quantum_chemistry_pl.py:132: # Coulomb integrals [#ref_integrals]_ evaluated using the Hartree-Fock
circuit/tutorial_quantum_chemistry_pl.py:141: # This implies that we need to map the fermionic operators onto operators
circuit/tutorial_quantum_chemistry_pl.py:158: # maps it to the qubit representation.
circuit/tutorial_quantum_chemistry_pl.py:160: qubit_hamiltonian = qchem.decompose(hf_file, mapping="jordan_wigner")
circuit/tutorial_quantum_chemistry_pl.py:231: # Within this approximation, a certain number of **active electrons** are allowed to
circuit/tutorial_quantum_chemistry_pl.py:309: #     J.T. Fermann, E.F. Valeev, "Fundamentals of Molecular Integrals Evaluation".
utils/vis_time_vqe_shuffle.py:140: ax[1].set_title('Speedup to accuracy', font, fontsize=fontsize)
utils/vis_time_qnn_new.py:39: base_acc = np.load(os.path.join(log_dir_ideal, 'acc_test_'+str(1)+'_'+str(h)+'_0.0_0_{}.npy'.format(seed)))
utils/vis_time_qnn_new.py:54: ts, accs = [], []
```

**verdict:** genuinely_absent

**note:** 

---

## study081

- repo: https://github.com/roedoejet/fastspeech2
- commit: `aabe8c26292ecf836979b0e7b1c33cb241f7b77a`
- paper claims: IDMUSHRA score, MUSHRA score, root mean square error
- code files: 67

Evaluation-shaped filenames:

- `evaluate.py`

Candidate lines (loose search, expect false hits):

```
README.md:49: Checkpoints should be named according to the number of training steps, so you will need to remove the dataset name from 
dataset.py:416: "Validation set  with size {} is composed of {} batches.".format(
synthesize.py:19: from text.symbols import MAPPINGS, TOKENIZERS
synthesize.py:105: g2p_norm = MAPPINGS[lang]["norm"]
synthesize.py:106: g2p = MAPPINGS[lang]["ipa"]
train.py:16: from evaluate import evaluate
train.py:171: model.eval()
train.py:172: message = evaluate(
evaluate.py:27: def evaluate(
evaluate.py:61: # Evaluation
evaluate.py:65: accs = []
evaluate.py:66: recalls = []
evaluate.py:67: precisions = []
evaluate.py:84: spe_classifier.eval()
```

**verdict:** genuinely_absent

**note:** 

---

## study071

- repo: https://github.com/yuvalkirstain/pickscore
- commit: `f79607ff68609c1e6dfa78cba38afeea4c248df1`
- paper claims: Accuracy, Aesthetic Score, CLIP-H text-alignment score, Comparison Win Rate, Lose rate, Percentage of instances, Percentage of prompts, Preference distribution, Tie rate, User preference, Win Rate, Win rate
- code files: 41

Evaluation-shaped filenames:

- `trainer/scripts/eval_preference_predictor.py`
- `trainer/utils/FID/fid_score.py`

Candidate lines (loose search, expect false hits):

```
README.md:28: pip install git+https://github.com/huggingface/accelerate.git@d1aa558119859c4b205a324afabaecabd9ef375e
README.md:39: # Only required for evaluation
README.md:59: model = AutoModel.from_pretrained(model_pretrained_name_or_path).eval().to(device)
README.md:89: # score
README.md:90: scores = model.logit_scale.exp() * (text_embs @ image_embs.T)[0]
README.md:93: probs = torch.softmax(scores, dim=-1)
README.md:140: python trainer/scripts/eval_preference_predictor.py
trainer/tasks/clip_task.py:6: from accelerate.logging import get_logger
trainer/tasks/clip_task.py:7: from accelerate.utils import LoggerType
trainer/tasks/clip_task.py:11: from trainer.accelerators.base_accelerator import BaseAccelerator
trainer/tasks/clip_task.py:36: def __init__(self, cfg: CLIPTaskConfig, accelerator: BaseAccelerator):
trainer/tasks/clip_task.py:37: super().__init__(cfg, accelerator)
trainer/tasks/clip_task.py:51: scores = torch.stack([image_0_scores, image_1_scores], dim=-1)
trainer/tasks/clip_task.py:52: probs = torch.softmax(scores, dim=-1)
```

**verdict:** unclear

**note:** 

---

## study087

- repo: https://github.com/dahyun-kang/ifsl
- commit: `d0b0c0d1b01c036eaae1470585764d1321ec5336`
- paper claims: ER, acc, class occurrence and segmentation masks, classification exact ratio, mIoU, segmentation mIoU
- code files: 39

Evaluation-shaped filenames:

- `fs-cs/common/evaluation.py`
- `fs-s/common/evaluation.py`

Candidate lines (loose search, expect false hits):

```
environment.yml:18: - ca-certificates=2021.10.26=h06a4308_2
environment.yml:19: - certifi=2021.10.8=py38h06a4308_0
environment.yml:215: - werkzeug==2.0.1
fs-cs/README.md:31: --benchmark {pascal, coco} \
fs-cs/README.md:44: ## :pushpin: Quick start: Evaluating authors' checkpoints
fs-cs/README.md:49: --benchmark {pascal, coco} \
fs-cs/README.md:56: --eval
fs-cs/README.md:59: To evaluate the `asnet-pascal-1way-1shot-resnet50-fold0` model, run:
fs-cs/README.md:63: --benchmark pascal \
fs-cs/README.md:70: --eval
fs-cs/README.md:86: <td colspan="4" align="center">4-fold validation folds</td>
fs-cs/README.md:89: <td>metric</td>
fs-cs/README.md:91: <td>seg. mIoU</td>
fs-cs/README.md:93: <td>seg. mIoU</td>
```

**verdict:** unclear

**note:** 

---

## study005

- repo: https://github.com/cross-domain-compositing/cross-domain-compositing
- commit: `cb7010062aa0d5654283d5bcc0af241c88940821`
- paper claims: CLIP-FID, CLIP-FID trade-off, feed-forward evaluation time, model inference time, performance, text generation success, trade-off curves, zero-shot text-to-image generation performance
- code files: 118

Evaluation-shaped filenames:

- `SVR/eval/eval.py`
- `SVR/eval/eval_2D_iou.py`
- `SVR/test/test.py`
- `SVR/test/test_external_cam.py`
- `SVR/test/test_external_image.py`
- `SVR/train_test_split.py`
- `configs/latent-diffusion/txt2img-1p4B-eval.yaml`
- `scripts/tests/test_watermark.py`
- `scripts_cdc/metrics.py`
- `scripts_cdc/metrics_single.py`

Candidate lines (loose search, expect false hits):

```
Stable_Diffusion_v1_Model_Card.md:77: Texts and images from communities and cultures that use other languages are likely to be insufficiently accounted for.
Stable_Diffusion_v1_Model_Card.md:110: - **Gradient Accumulations**: 2
Stable_Diffusion_v1_Model_Card.md:114: ## Evaluation Results
Stable_Diffusion_v1_Model_Card.md:115: Evaluations with different classifier-free guidance scales (1.5, 2.0, 3.0, 4.0,
Stable_Diffusion_v1_Model_Card.md:119: ![pareto](assets/v1-variants-scores.jpg)
Stable_Diffusion_v1_Model_Card.md:121: Evaluated using 50 PLMS steps and 10000 random prompts from the COCO2017 validation set, evaluated at 512x512 resolution
README.md:101: We use [ChamferDistancePytorch](https://github.com/ThibaultGROUEIX/ChamferDistancePytorch.git) for chamfer distance eval
README.md:132: Follow the steps below to test and evaluate in-the-wild images.:
README.md:138: 5. Run `python ./SVR/eval/eval_2D_iou.py` to evaluate 2D-IOU on in the wild images. Remember to specify the input/output
notebook_helpers.py:42: pl_sd = torch.load(ckpt, map_location="cpu")
notebook_helpers.py:48: model.eval()
notebook_helpers.py:190: temperature=1., noise_dropout=0., score_corrector=None,
notebook_helpers.py:201: score_corrector=score_corrector,
notebook_helpers.py:251: score_corrector=corrector, corrector_kwargs=corrector_kwargs,
```

**verdict:** genuinely_absent

**note:** 

---

## study050

- repo: https://github.com/hmhyau/rl-intention
- commit: `29c84fd9abaa6149fc170531d0ae904fb23047a4`
- paper claims: MC, TD, similarly
- code files: 17

Evaluation-shaped filenames: **none**

Candidate lines (loose search, expect false hits):

```
environment.yml:9: - ca-certificates=2020.10.14=0
environment.yml:10: - certifi=2020.6.20=py37_0
environment.yml:98: - werkzeug==1.0.1
deep_class.py:372: update = torch.zeros(batch_size, *list(map(lambda x: x.n, self.observation_space)), self.policy.n_actions).to(self.devic
deep_class.py:613: update = torch.zeros(batch_size, *list(map(lambda x: x.n, self.observation_space)), self.policy.n_actions).to(self.devic
train_blackjack.py:18: # Cannot check consistency with exact equivlency due to precision
wrappers.py:60: return tuple(map(float, state))
wrappers.py:70: return tuple(map(int, state))
wrappers.py:81: return np.array(tuple(map(float, list(self.env.decode(observation))))).astype(np.float32)
buffer.py:57: data = Transition(*tuple(map(self.to_torch, data)))
buffer.py:97: return tuple(map(as_list, data))
policies.py:44: self.n_obs = tuple(map(lambda x: x.n, self.ob_space))
policies.py:92: self.n_obs = tuple(map(lambda x: x.n, self.ob_space))
policies.py:169: self.n_obs = np.array(tuple(map(lambda x: x.n, self.ob_space)))
```

**verdict:** unclear

**note:** 

---

## study029

- repo: https://github.com/zhimengj0326/gradient_rewiring_editing
- commit: `899134695c291b65f3b5e8e7461e6da4d9607d9d`
- paper claims: Acc, Accuracy (Acc), DD, DrawDown, DrawDown (DD), SR, Success Rate (SR), accuracy, accuracy drop, accuracy dropdown, average accuracy drop, drawdown
- code files: 34

Evaluation-shaped filenames:

- `eval.py`
- `scripts/eval.sh`
- `scripts/eval_gre.sh`
- `scripts/eval_gre_plus.sh`

Candidate lines (loose search, expect false hits):

```
environment.yml:12: - ca-certificates=2023.7.22=hbcca054_0
environment.yml:60: - certifi==2023.5.7
README.md:25: * Standard evaluation:
README.md:27: bash scripts/eval.sh $GPU_NUMBER
README.md:29: * Evaluation using Gradient Rewiring (GRE):
README.md:31: bash scripts/eval_gre.sh $GPU_NUMBER
README.md:33: * Evaluation using the extended version, GRE+:
README.md:35: bash scripts/eval_gre_plus.sh $GPU_NUMBER
eval.py:148: print(f'before edit, train acc {train_acc}, valid acc {valid_acc}, test acc {test_acc}')
eval.py:162: seq_results = trainer.eval_edit_quality(node_idx_2flip=node_idx_2flip,
eval.py:167: eval_setting='sequential',
eval.py:174: ind_results = trainer.eval_edit_quality(node_idx_2flip=node_idx_2flip,
eval.py:179: eval_setting='independent',
eval.py:186: batch_results = trainer.eval_edit_quality(node_idx_2flip=node_idx_2flip,
```

**verdict:** unclear

**note:** 

---

## study083

- repo: https://github.com/joseangelmartinb/gklr
- commit: `845560a634478d0b9786c1cf2cd93b369c67a3c1`
- paper claims: (none extracted)
- code files: 30

Evaluation-shaped filenames:

- `tests/conftest.py`

Candidate lines (loose search, expect false hits):

```
docs/conf.py:238: # Custom sidebar templates, maps document names to template names.
docs/conf.py:241: # Additional templates that should be rendered to pages, maps page names to
docs/conf.py:312: # -- External mapping --------------------------------------------------------
docs/conf.py:313: python_version = ".".join(map(str, sys.version_info[0:2]))
docs/index.md:30: ```eval_rst
src/gklr/kernel_utils.py:2: from sklearn.metrics import pairwise
src/gklr/kernel_matrix.py:8: from sklearn.utils.validation import check_array
src/gklr/kernel_matrix.py:9: from sklearn.metrics.pairwise import pairwise_kernels
src/gklr/kernel_matrix.py:441: X = check_array(X, accept_sparse='csr')
src/gklr/kernel_matrix.py:450: " in inefficient evaluation of the full kernel.")
src/gklr/kernel_matrix.py:467: # Sample n_components elements from data proportionally to these scores
src/gklr/kernel_matrix.py:479: basis_kernel = pairwise_kernels(basis, metric=self.kernel,
src/gklr/kernel_matrix.py:492: """Apply feature map to X.
src/gklr/kernel_matrix.py:494: Computes an approximate feature map using the kernel
```

**verdict:** unclear

**note:** 

---

## study066

- repo: https://github.com/STomoya/ResNeSt
- commit: `3b2b4f4a73d138bb1e4ff2b8695be4cf950543da`
- paper claims: AP, Accuracy (%), COCO AP, Throughput (img/sec), acc, accuracy, accuracy trade-off, box mAP, inference speed, mean average precision, number of parameters, top-1 accuracy
- code files: 4

Evaluation-shaped filenames: **none**

Candidate lines (loose search, expect false hits):

```
README.md:22: - Evaluate the model
```

**verdict:** genuinely_absent

**note:** 

---

## study047

- repo: https://github.com/saurjya/asteroid
- commit: `591781278dbf38deac29dfab93920c67c5e1afb5`
- paper claims: SDRi, SI-SNR improvement, SI-SNRi, WER, signal-to-distortion ratio improvement, word error rate
- code files: 429

Evaluation-shaped filenames:

- `.github/workflows/test_asteroid_package.yml`
- `.github/workflows/test_docs.yml`
- `.github/workflows/test_formatting.yml`
- `.github/workflows/test_model_consistency.yml`
- `.github/workflows/test_torch_hub.yml`
- `asteroid/metrics.py`
- `asteroid/utils/test_utils.py`
- `egs/BBCSO/DPTNet/eval.py`
- `egs/MedleyDB/ConvTasNet/eval.py`
- `egs/MedleyDB/DPRNN/eval.py`

Candidate lines (loose search, expect false hits):

```
CODE_OF_CONDUCT.md:17: * Gracefully accepting constructive criticism
CODE_OF_CONDUCT.md:31: Project maintainers are responsible for clarifying the standards of acceptable behavior and are
CODE_OF_CONDUCT.md:43: e-mail address, posting via an official social media account, or acting as an appointed representative at an online
CHANGELOG.md:35: - [src&tests] Add MetricTracker (#394)
CHANGELOG.md:37: - [src] Track transcriptions in WerTracker (#414)
CHANGELOG.md:93: - [src&tests] Add shape checks to SDR and MSE losses (#299)
CHANGELOG.md:109: - [src&tests] Make `get_metrics` robust against metrics failures (#275)
CHANGELOG.md:170: - [models] Add pretrained DeMask name to URL mapping
CHANGELOG.md:186: - [hub] Remove args in hub models, don't accept positional args after kwargs
CHANGELOG.md:275: [src] Enable using Zenodo without api_key argument (set ACCESS_TOKEN env variable)
CHANGELOG.md:282: [egs] Fix: remove shuffle=True in validation Loader (lightning error) (#124)
CHANGELOG.md:283: [egs] Corrections on LibriMix eval and train and evals scripts  (#137)
CHANGELOG.md:284: [egs] Fix wavfiles saving in eval.py for enh_single and enh_both tasks (closes #139)
CHANGELOG.md:285: [egs] Fix wavfiles saving in eval.py for enh tasks (estimates)
```

**verdict:** unclear

**note:** 

---
