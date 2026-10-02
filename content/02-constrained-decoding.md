# How a Grammar Changes AI-Generated Mathematical Proof Steps

*A quick note on how the sampling works, some saved results, and some notes on how the grammars accept the models' outputs.*

Lean is a language and tool for writing proofs that a computer can check. Commands to make steps in a proof are called tactics. We're looking at grammars for these proof steps.

Updated September 5, 2026 to make this a more complete article than the one from August 22. This has more details on the mechanics of decoding, examples to trace through, exact counts, and some corrections in the definitions of metrics. The key change is that we no longer consider the CFG accepting of inputs on the basis of whether they're valid Lean, and hence the "latency" and fraction of lines presented here differ from what might be implied by the original post. If the distinctions aren't relevant to what brought you here, the [original article is here](https://stanleyngugi.netlify.app/archive/revisions/2026-08-22-grammar-constrained-decoding-lean-original). If the evidence and how to reproduce it is what brought you here, see [the evidence and reproduction notes](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/evidence.md).

How does grammar constrained decoding change what a model outputs? When we sample from a language model, at each step we compute a distribution over the next token. The grammar modifies this distribution to change what we sample. Since we sample different tokens, this will change the output of the model in general.

Here, I'll show an example with a permissive grammar for Lean's tactic language, run on Qwen2.5-Coder-7B-Instruct. When we constrain to the grammar, 640/640 of the outputs (after "cleaning") have first lines accepted by the grammar I use to score the outputs. (I use vLLM and llguidance to do the sampling.) Without the grammar, I get 420/640 on the same prompts.

In the [first article](/posts/2026-08-22-lean-tactic-language-cfg.html), I explained why I think it's useful for the grammar to be permissive. In this article, I'll explain how the sampling works, show the results (since I saved them and they're not that big), and talk a bit about how the outputs differ depending on whether or not they're generated with the grammar.

This is an experiment about how the model's output distribution changes; it doesn't involve running the model in Lean or training any models. Some related avenues of investigation might be: what keywords are used, how often are things left unfinished, how often does the model make "admissions", how diverse are the strings, how long the requests take, and what happens when we look at something besides the first line of the output.

## What exactly does autoregressive grammar aware decoding do?

Autoregressive grammar aware decoding is a procedure to sample from an autoregressive model where a token `v` is only allowed to be sampled if, after decoding it to a character sequence, the prefix of generated characters can still be completed to a string in the language of the grammar.

In more detail, let’s say the token sequence sampled so far is `x`. Then, instead of sampling the next token `v` according to <i>p</i>(<i>v</i> ∣ <i>x</i>), the distribution is modified to: 

<div class="equation" role="math" aria-label="q of v given x equals p of v given x times M sub G of x v, divided by the sum over u of p of u given x times M sub G of x u">
<i>q</i>(<i>v</i> ∣ <i>x</i>) = <span class="fraction"><span class="numerator"><i>p</i>(<i>v</i> ∣ <i>x</i>) <i>M</i><sub>G</sub>(<i>x</i>, <i>v</i>)</span><span class="denominator">∑<sub>u</sub> <i>p</i>(<i>u</i> ∣ <i>x</i>) <i>M</i><sub>G</sub>(<i>x</i>, <i>u</i>)</span></span>
</div>

Here, <i>M</i><sub>G</sub>(<i>x</i>, <i>v</i>) ∈ {0, 1} is a mask indicating whether or not `v` is a valid continuation of `x` (assuming no other mask-like modifications to the sampling procedure, like nucleus, presence penalty, etc). Intuitively, the sampling distribution is set to 0 for invalid choices, and renormalized. This changes the sampling distribution (even if the underlying model weights are unchanged), and since future tokens are conditioned on the changed distribution, it changes future probabilities too.

| Hypothetical token fragment | Before masking | Allowed? | After masking |
|---|---:|---|---:|
| `mul_comm` | 0.50 | Yes | 0.714 |
| `h1` | 0.20 | Yes | 0.286 |
| closing fence | 0.20 | No | 0 |
| end-of-sequence | 0.10 | No | 0 |

As an example, suppose the above table contains a subset of all possible next token fragments, and their respective probabilities according to the model. Here, the grammar is permissive, and allows any name at this point in the prefix, but does not allow it to be completed yet. Then, <i>q</i>(<i>v</i> ∣ <i>x</i>) would be the modified probabilities that are actually used for sampling. To be clear, these are not the logits used in the experiment, but are provided for teaching purposes.

Notice that the ratio is still 2.5, but this is not necessarily true for all subsequent tokens. It is also worth noting that although it might look like the decoder is providing a score of how likely a token is to be part of a theorem, it is only providing a way to exclude certain choices. Finally, be aware that although the masking is done on a local level, the resulting distribution is not exactly equivalent to sampling from the original distribution conditioned on the whole string being valid.

It might be helpful to see some pseudocode of how the loop works:

```python
# Pseudocode: the real engine operates on tokenizer-aware masks.
while not finished:
    logits = model.next_token_logits(prompt, generated)
    allowed = matcher.allowed_token_ids()
    logits[~allowed] = float("-inf")
    token = sample(logits)
    matcher.accept(token)
    generated.append(token)
```

## It’s not a tactic yet!

Let’s take the (highly restricted for the purposes of the first article) rewrite rule grammar as an example:

```lark
start: "rw" "[" name ("," name)* "]"
name: /[A-Za-z_][A-Za-z0-9_'.]*/
%import common.WS
%ignore WS
```

Given the partial generation `rw [`, it’s valid to start generating an identifier. Given `rw [mul_`, it’s still valid to continue generating the identifier. But, once the generation is `rw [mul_comm`, it’s now valid to generate a closing bracket to complete the generation, or a comma to start generating another element of the list. Crucially though, it’s not valid to stop generation at this point!

It’s important to note that the model isn’t generating non-terminals or terminals of this grammar, but rather a sequence of tokens from its vocabulary. So it’s wrong to check each token individually against the grammar, or even just the first character of the token.

There’s also a subtlety around how generation can be stopped: in particular, it’s possible for the generation to be stopped due to some external factor (e.g. running out of tokens, or some other type of interruption) at a point where the generation is still a valid prefix of the grammar, but not a valid complete generation. It’s important to note that these are two different things, and that in a real experiment, one should record the reason why generation was stopped, and additionally validate the generations against the grammar actually used for generation.

Unfortunately, the original files don’t contain this information, so for now, we can’t tell from them whether generation stopped because it was complete, or measure the number of tokens used for the completion.

<figure>
<img src="/assets/cfg/decoding.svg" width="760" height="540" alt="Model probabilities and tokenizer-aware grammar state jointly determine allowed tokens; masked sampling updates both the generated prefix and matcher state." loading="lazy">
<figcaption>The intervention happens during sampling. Post-hoc scoring is a separate operation and may even use a different grammar.</figcaption>
</figure>

## Which grammar was used for generation?

The generation grammar that was used is [`post2-constrained-decoding/grammar_lean.lark`](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/post2-constrained-decoding/grammar_lean.lark), which was adapted from the scoring grammar to work with the guidance backend (this mostly involved adding explicit whitespace and removing the Lark-specific priorities, and avoiding a Lark-specific lookahead expression in the case patterns).

The generation grammar is not (as far as I’m aware) provably equivalent to the scoring grammar. In fact, there are a few small differences (to do with which characters are allowed in identifiers, how case is handled, and some structural differences). However, the two grammars share what (to me) seem like the most important features, namely that they both allow very arbitrary arguments, and they both have a fallback option of just allowing any identifier:

```lark
generic_tac: ident (_WS args)?
ident: /[A-Za-z_\u0370-\u03FF][A-Za-z0-9_'!\u0370-\u03FF]*/
args: /[^\n]+/
_WS: /[ \t]+/
```

This means that the grammar is quite permissive. For example, it will accept just saying sorry (because sorry is an identifier), or it will accept things like exact sorry (because this is a named tactic with arbitrary arguments). It will even accept various English sentences, as long as they start with an identifier. (Some of the comments in the grammar claim that certain keywords are not allowed by the grammar, but this is not true - the language of the grammar has not been changed, only some of the comments).

Of course, even though the grammar is permissive, it still rules out some things, and so it still changes the distribution of outputs. The fact that I saved some Qwen results does indicate that this particular intervention is associated with the scored distribution of outputs. However, it does not indicate that the output will always parse.

## What was the exact task and prompt used for the Qwen comparison?

The task was to generate a single first tactic, given the statement of a theorem. The system message was:

```text
You are a Lean 4 proof assistant. You output only Lean 4 tactics.
```

And the user message was:

````text
Below is the statement of a real Lean 4 (Mathlib) theorem.

```lean
{stmt}
by
```

Output exactly ONE Lean 4 tactic line that would be a reasonable FIRST
proof step for this theorem. Output only the tactic itself, nothing else.
````

This was the prompt format used in the historical experiments, for reference. It is no longer actively maintained and is known to be not great. In particular, the prompt is not formatted as a complete and compilable theorem declaration. This was not a problem at the time the experiment was performed, since the experiment didn't bother to check that each prompt was in fact a valid theorem statement.

More recently, it has been noticed that at least some of the 80 extracted statements used as prompts appear to contain context that is not included in the prompt, and therefore the prompt is not a complete theorem statement. For instance, the currently saved prompt for "card_pow_le" contains two parts of separate branches of a proof, as well as a subsequent theorem declaration, making it fairly obvious that this is not a well-extracted theorem statement. This was not caught at the time because the prompts were selected randomly from the available statements, and so not all of them were checked for validity.

Both of the Qwen conditions were given the same set of prompts, but due to the issues described above, it is not clear how well the results generalize to a more realistic set of theorem statements. Furthermore, the task is not the same as predicting the next tactic in a proof, since the model is not given the current state of the proof.

## Configuration and artifacts

The historical stack for this project was vLLM 0.10.2 (with the guidance backend) on an RTX A5000, using the Qwen2.5-Coder-7B-Instruct model. The Qwen driver used the following settings:

| Setting | Value |
|---|---|
| Saved prompt set | 80 extracted statements |
| Samples per statement | 8 |
| Requests per sample | One, with `n=1` |
| Temperature | 0.8 |
| Top-p | 0.95 |
| Maximum output tokens | 64 |
| Task | One first tactic |
| Scoring unit | First nonempty line after cleanup |

The served model alias in the driver was `m`. The historical files don’t include a full server manifest.

Note that the historical JSONL files do not contain information about the specific model revision used, and so the model revision is not recorded here. This is the best information available.

This involves a request-level modification:

```python
extra_body = {
    "guided_grammar": grammar_text,
    "guided_decoding_backend": "guidance",
}
```

The unconstrained version simply doesn't include this in the request body. The [full driver](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/post2-constrained-decoding/gen_eval.py) is still available in the repo if that's unclear. Note that this reflects the state of the API for the pinned version of the serving stack at the time; the API for the most current version of vLLM may differ.

Note that while the raw generation files are unchanged, the analyzed versions in `analysis/` are now correct (they record hashes of their inputs to make it clear which files they go with, which helps if people want to recover the artifacts locally for some reason).

## On Scoring Cleanup

The scorer does some cleanup, it doesn't just blindly try to parse whatever comes out of the model. In particular the code does:

```python
text = remove_outer_fences(text.strip())
lines = [line.strip() for line in text.splitlines() if line.strip()]
tactic = lines[0] if lines else ""
```

So for example if the model outputs a fenced block containing `simp`, followed by `something` and `something_else`, the scorer will extract simp and score that. But if it outputs e.g. the chain of thought before the actual output, it will try to score the first line of that, which likely isn't a valid tactic.

It does also generate the multiline note from the original scorer, so it's not like that information is lost.

It'd be weird to compare constrained generation's cleaned up outputs to unconstrained generation's raw outputs. When originally trying out constrained generation on these benchmarks, the comparison was between unconstrained generation with cleanup vs constrained generation with cleanup. The "cleanup" is pretty minimal, it's basically just there to handle models that wrap their output in a markdown code block. The original Qwen scorer also does this cleanup for both unconstrained and constrained generations.

The scorer was broken because it forgot to import `os`. It’s fixed [here](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/post2-constrained-decoding/score.py), but it scores to a different place, so that when scores are regenerated they don't overwrite the original csvs. The historic classification can be computed by applying the same id heuristic.

## Scoring Qwen on the same thing

|Measurement|Unconstrained|Constrained|
|---|---|---|
|Samples|640|640|
|Named CFG alternative|388|592|
|Generic fallback|32|48|
|Rejected by CFG|220|0|
|Accepted by CFG|420 (65.625%)|640 (100.000%)|
|Leading keyword in corpus|385/640 (60.156%)|584/640 (91.250%)|
|At least one identifier flag|319/640 (49.844%)|339/640 (52.969%)|
|Mentioned sorry or admit|2/640 (0.313%)|16/640 (2.500%)|
|# distinct strings per statement|7.10|7.00|
|Mean request latency|0.3035 s|0.3473 s|

<figure>
<img src="/assets/cfg/qwen-acceptance.svg" width="820" height="410" alt="Of 640 Qwen samples in each condition, the unconstrained run has 388 named matches, 32 generic matches, and 220 rejections; the constrained run has 592 named matches, 48 generic matches, and no rejections." loading="lazy">
<figcaption>Classification of first cleaned lines. These are CFG outcomes, not Lean execution outcomes.</figcaption>
</figure>

This is an improvement of 34.375 percentage points, or 220 more accepted strings on the fixed budget that was used.

The leading keyword statistic is not directly relevant, but does provide some corroborating evidence that something changed. The table of keywords was computed using the heuristic extractor of corpus data discussed in the [first article](/posts/2026-08-22-lean-tactic-language-cfg.html). It is not the set of tactics that were actually loaded into Lean for LLM queries.

The ablation study performed in the [first article](/posts/2026-08-22-lean-tactic-language-cfg.html), wherein the grammar was made smaller, is exactly the same with respect to acceptances. This is evidence that the set of acceptances is broadly the same, and that the specific choice of productions named as "tactics" wasn't relevant.

## Saved examples

Below are a few saved samples from the scorer. These examples should not be taken as representative of how often different categories of measurements show up for a given model, but are instead meant to illustrate how the different categories work. For each sample, we include the `goal_id` and `sample_idx` so that they can be found in the corresponding jsonl file. For each example, we also save the raw and cleaned sample text and classifications in `analysis/examples.json`.

**Example 1:** The sample is:

```text
`apply comp_idem`
```

(from `unconstrained__qwen.jsonl`, goal 29184, sample 1). This sample is rejected by the context-free grammar checker due to the formatting at the beginning of the sample. The cleaner does not remove the backticks, since it only strips triple backticks from the beginning and end of the sample. This example is meant to illustrate that the current cleaner doesn't deal with all formatting issues, but that a change in the cleaning code would have an effect on the sample score. In this case, removing the backticks would change the score, though it wouldn't necessarily make the tactic correct (since we don't know if `comp_idem` is even a valid identifier that resolves to something).

**Example 2:** The sample is:

````text
induction n with | zero => simp | succ n ih =>
  have h₁ : deriv (iteratedDeriv n f) = iteratedDeriv (n + 1) f := by ring
  rw [h₁] at ih
  simp [ih]
```
````

(from `unconstrained__qwen.jsonl`, goal 36579, sample 7). The "first line" scorer classifies this as a named induction with the multiline note, since the first line matches the named induction alternative in the CFG. The issue is that the argument catch-all part of the grammar accepts this entire line. This sample illustrates that the score is based on which line is chosen, and is agnostic to whether or not that line is part of a complete proof structure.

**Example 3:** The sample is:

```lean
have hB_cont := continuous_comp (continuous_id ∘ f) hg.continuous; sorry
```

(from `unconstrained__qwen.jsonl`, goal 110604, sample 2). This sample is classified as being accepted by the grammar, but also using an admission, since the have statement at the beginning is accepted by the grammar, but the lexical scorer recognizes the sorry in this sample. Both of these classifications are correct, and this illustrates that these scorers are looking for two different things.

**Example 4:** The sample is `rewrite category.id_comp` (from `constrained__qwen.jsonl`, goal 29184, sample 3). This sample is classified as being a generic fallback. This example shows that even for the constrained data, not all samples choose a named production.

## Does it preserve diversity of similar strings?

To get this value, all outputs were grouped by each statement, and the number of unique strings after cleaning was counted. (There are only 8 samples per group, so the maximum value is 8.)

This suggests that the amount of duplication in exact strings has not gone up dramatically in this small run. This also does not necessarily mean that it is preserving the diversity of strategies for proving a theorem; for example, "simp [h1]" and "simp [h2]" would be counted as different, even though they may have the same effect. Moreover, two completely different strings may have the same effect of failing immediately. On the other hand, one of these tactics may include a large amount of internal proof search.

If and when this is tested on actual proving ability in the future, the diversity of unique successor states, or the diversity of families of tactics or proofs that can successfully prove a theorem, may be better metrics for determining how the model performs. (At that point, an actual evaluator would need to be declared to determine how equivalency is measured.)

Note that this was clustered by each of the 80 statements, and any generalization to the larger pool of problems should take this into account when calculating uncertainty. These values are exact for the current files. This is not a confidence interval for a future run with a different set of theorems or a different model.

## What is the name checking rate?

Some keywords, local binders, common core names, and generated names are excluded, and any remaining names in the arguments are looked up in a table generated from the source.

This is not a perfect oracle for hallucination; names are looked up by their short name, so this may approve a hallucinated name in a different namespace, flag a local variable that was not recognized properly, or miss a real declaration in the core library that was not found in the scanned roots. Moreover, a name may be introduced in the proof rather than referenced.

This rate should more accurately be described as the percent of generations with at least one flagged identifier. It does not necessarily mean that approximately half of the generations include a hallucinated reference to a non-existent Lean declaration.

A common point of confusion is that even when using the same checker, its bias is not cancelled out since the constraints change the form of generations, and different forms trigger the heuristic differently. A manually checked sample or environment-aware name resolution would help establish what those flags mean. At the moment, all this comparison is telling me is that the constraints are changing some flag on the LLM in a certain way.

That said, it is useful information - in this case it shows that intervening on the grammar was not able to remove some heuristic applied for dictionary words, which makes sense because the grammar does not constrain most of the argument slots.

## Importance of latency precision

The mean of both of these is 0.3 when rounded, but the underlying data is 0.30353125 vs 0.347296875, so the average request latency was ~14.4% higher.

I want to be careful with what causal claims I make about this difference, since the requests are not identical and there are a bunch of other factors that could cause this difference, but I wanted to point out that it would be hard to make this kind of comparison with the historical artifacts since they don't contain information about the number of tokens generated (to normalise for different length generations) nor do they repeatedly run the same request interleaved.

In the absence of more careful measurement, I would just point out that both runs took under a second on average and that one was higher than the other. If I were to run this experiment today I would log all of the information necessary to make a throughput comparison (number of input/output tokens, time to first token, total time taken, whether the request was completed, server configuration, warmup policy, etc) as well as accounting for the fact that validation involves retries.

## Goedel Experiments

This is another set of very valuable experiments, but the issues described above about interface to generations and scoring by unit still apply.

Just for reference, the model was Goedel-Prover-V2-8B (from [the paper](https://arxiv.org/abs/2508.03613)). The artifacts that I recovered were:

|Artifact|Num samples|Num statements|Interface and budget|
|---|---|---|---|
|Unconstrained first step|640|80|Chat-style first step setup with 64 token budget for the driver|
|“Constrained” first step|640|80|Same as above, although I’m not sure that the setup was constrained correctly|
|Native full proof|139|69|Text completion interface with the statement + an unclosed Lean proof code fence, intended to sample two samples per statement with a 500 token budget|

Note that for the native model I’m using the statement + an unclosed Lean proof code block as the prefix, and asking the model to complete this. This differs from the first step artifacts where a chat style instruction was used. Note also that this artifact is incomplete (it is supposed to contain two samples for each of the 80 statements).

To be clear, the “yield” number was calculated by running a script which, for each output: if there was at least one complete code fence in the output, selected only the lines within the first complete code fence; otherwise, selected all lines from the output; removed empty lines and lines which were headings or specific comments; stripped leading and trailing whitespace and trailing commas; checked whether the remaining string was accepted by the CFG.

Running this script, I get the following numbers for the fraction of selected lines accepted by the CFG:

|Artifact|Num selected lines|Fraction accepted by CFG|
|---|---|---|
|Qwen unconstrained|670|64.9%|
|Qwen constrained|640|100.0%|
|Goedel native full proof|1970|49.9%|
|Goedel “constrained”|640|84.5%|

This number is not the same as the fraction of tokens sent to Lean, as (1) it’s a fraction of lines rather than tokens and (2) it doesn’t necessarily correspond to valid complete proofs since a line may be part of a multiline term/proof etc.

It’s worth pointing out that for the native Goedel file, 130/139 of the first cleaned lines of each output are accepted by the CFG, so there’s no typo in the numbers above!

For the constrained Goedel file, the number is 541/640, or 84.53%. However, the CSV files for the scores only contained a part of this, so the numbers in those CSVs are for a smaller set. Rather than try to combine the partial denominator with the complete denominator for the recovered file, I’ve just reported the number for the recovered file here.

## How to prove constraint activity?

In the experiments for the original PR, there were some weird outputs. It was thought they were due to parallel sampling causing vLLM to revert to another backend. However, it might be useful to have a more general proof that this bug exists in vLLM, and what the cause of it is. This is a research log of trying to prove that the issue is due to the way serving works, as the fact that it occurs when sampling in parallel can't be proven only by looking at saved generations.

For this, it would be helpful to have a grammar for a generation, and an output which that generation can't output. For instance, one could create a tiny grammar which only allows the word "rfl" to be output, and then show that the server returns a generation with "simp" after getting a finish reason of "complete". However, if the grammar allows arbitrary text starting with an identifier, then it's harder to show that an English sentence generated by the model shouldn't have been generated.

Another way to prove that the constraint is being enforced could be to try and enforce it, and see if it works. This could entail compiling the grammar using the backend, and then checking that each returned string (with finish reason "complete") is in the language. Any errors from the backend should also be stored, along with the reason the generation terminated for. This should probably only be done either with n=1 or with parallel sampling, for a minimal example.

One could also simply check if generations are accepted after the fact. However, noting that 100% of generations are accepted by a different, more general grammar is not sufficient to show that masking is being done. Similarly, noting that there are no markdown fences in a generation is only a smoke test for a specific issue, not a general way to show that the constraints are being enforced.

The repo has been changed to have n=1 in the driver (it was always like that historically), and the claims about what is and isn't done by the backend have been narrowed. A new run should save more information about if the constraints are being enforced.

## Handling reserved words and limited retries

Note that "sorry" was observed in the above. It's not part of the grammar, except via the generic identifier. Even if one were to remove that, and ensure that the top level can't generate "sorry", one could still generate e.g. `exact sorry` because the term doesn't have any restrictions on it.

There is a wrapper which will check lexically if the output is acceptable, and if not, will resample a limited number of times. Note that this is not a way to certify that something is in a language, and also that it may reject things which are in the language (if it's simply checking that a word doesn't appear with word boundaries, then it will reject valid outputs which have that word in a comment or string, for example).

Finite forbidden-word exclusion can be represented by suitable lexical constructions even without regex lookahead; whether a particular engine accepts a convenient expression is an implementation question. More importantly, banning a spelling and verifying a proof’s dependencies are different goals.

For an idealized independent violation probability `p`, unlimited rejection sampling needs an expected `1 / (1 - p)` attempts. At `p = 0.025`, that is about 1.026. The arithmetic explains the old “1.03” estimate, but it is not measured end-to-end overhead. A bounded wrapper can exhaust its attempts, and real retry distributions need not satisfy the simplifying assumption.

## Optional reasoning is a separate experiment

The original architecture proposed allowing informal reasoning before activating the formal grammar. The saved Qwen experiment instead asks for a tactic directly. Those arrangements should be distinguished:

```text
A: prompt → constrained tactic
B: prompt → free reasoning → constrained formal block
```

[CRANE](https://arxiv.org/abs/2502.09061) studies reasoning-augmented constraints and motivates this distinction. It does not establish which arrangement works better for these Lean prompts. Nor does the fact that a formal language is infinite prove that every restriction preserves every useful reasoning path.

A controlled comparison would hold total generation cost fixed, account for the reasoning tokens, and implement switching correctly across tokenizer boundaries. Informal tokens may contribute to the eventual answer; their absence from a tactic grammar is not evidence that they were wasted.

This matters for the interpretation of the native full-proof outputs. A model’s preferred generation interface, including any reasoning or scaffolding, should be understood before its lines are classified as losses. The right experiment can still find that direct constrained tactics are more efficient. That result needs to be measured rather than assumed.

## What the experiment does and does not establish

The main supported result is a substantial increase in first-cleaned-line CFG acceptance for the saved Qwen run, together with more corpus-recognized leading keywords and similar exact-string diversity.  Identifier flags remain common. Recorded average latency is higher in the constrained condition. The grammar itself remains permissive.

As called out in the header, this experiment doesn't directly measure whether the resulting strings are accepted by the Lean parser, or whether the tactics complete successfully, or whether the proofs complete, or how many tokens it saves, or how well it trains, etc. Lean does have some parser and elaborator feedback that happens before the end, so it's not entirely silent, but still, this doesn't measure that either.

Regarding the training point, it's not quite true that outputs which fail to be produced don't get optimized for. They can receive below-average group rewards, so they do contribute an optimization signal. For an explanation of the algorithm, see e.g. this [DeepSeekMath article](https://arxiv.org/html/2402.03300v3). That said, it's true that in general the number of rollouts contributing to a gradient step won't be given by the product of the group size and the syntax acceptance.

There's a lot of related work on generating tactics according to a grammar. One of the earliest is probably [ASTactic](https://proceedings.mlr.press/v97/yang19a/yang19a.pdf). However, this is not in the context of a pre-trained LLM, and instead of constraining generation by masking the token vocabulary, they use a different approach. Another related project, also targeting Lean, is the public [LeanGCD project](https://ai.math.uw.edu/projects/spring-2026/) on generating constrained output for Lean. While this isn't the only project of its kind, hopefully this article is useful for having an experiment that anyone can inspect.

## Things to do before trying to extend this

The associated git repo has been modified to be a little easier to work with. It saves the jsonl input files and the original csvs, and stores the other output files separately. To run the analysis, which is all CPU, and doesn't require the GPU serving, run:

```bash
pip install -r requirements-analysis.txt
python analysis/audit.py
python post2-constrained-decoding/score.py qwen
python post2-constrained-decoding/yield_analysis.py
python -m unittest discover -s tests
```

The file `analysis/audit.json` has various meta-information about the run, including the hashes of the raw files, the number of samples and goals, the total number of classifications and lines, the time taken for each, and the number of lines with each classification compared to the version with reduced grammars. The figures in the article are also generated from this. (Some of these numbers would be hard to reconstruct exactly, so here’s a [description of the provenance of the files](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/provenance.md).)

Proof-state interaction and training are in a separate project, `lean-proving-experiments`, which also contains the list of open questions. The [repository’s scope notes](https://github.com/stanleyngugi/ai-proof-grammars#scope-separation) explain the separation. Some of the things to try next with the CFG experiment are to extend the supported grammars, to extend the diagnostics for how often the enforcement is helping, to make the inputs to the experiment more faithful, and to compare the interfaces for the output in a controlled way.

## References

<div class="refs">
<p>Hui, B., et al. (2024). <a href="https://arxiv.org/abs/2409.12186">Qwen2.5-Coder Technical Report</a>. arXiv:2409.12186.</p>
<p>Lin, Y., et al. (2025). <a href="https://arxiv.org/abs/2508.03613">Goedel-Prover-V2: Scaling Formal Theorem Proving with Scaffolded Data Synthesis and Self-Correction</a>. arXiv:2508.03613.</p>
<p>Guidance contributors. <a href="https://github.com/guidance-ai/llguidance">llguidance</a>. Tokenizer-aware grammar constraints and structured generation.</p>
<p>Kwon, W., et al. (2023). <a href="https://arxiv.org/abs/2309.06180">Efficient Memory Management for Large Language Model Serving with PagedAttention</a>. SOSP 2023. The vLLM serving system.</p>
<p>Banerjee, D., Suresh, T., Ugare, S., Misailovic, S., and Singh, G. (2025). <a href="https://arxiv.org/abs/2502.09061">CRANE: Reasoning with constrained LLM generation</a>. arXiv:2502.09061.</p>
<p>Shao, Z., et al. (2024). <a href="https://arxiv.org/abs/2402.03300">DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models</a>. arXiv:2402.03300. Introduces GRPO.</p>
<p>Yang, K., and Deng, J. (2019). <a href="https://proceedings.mlr.press/v97/yang19a.html">Learning to Prove Theorems via Interacting with Proof Assistants</a>. ICML, PMLR 97, pp. 6984–6994. Introduces ASTactic and CoqGym.</p>
<p>University of Washington AI for Math. <a href="https://ai.math.uw.edu/projects/spring-2026/">LeanGCD</a>. Spring 2026 project listing; cited as related ongoing work.</p>
</div>
