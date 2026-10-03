# Grading Mathematical Answers Without Precomputed Answer Keys

> MathCheck RL uses environment-owned specifications to turn bounded mathematical
> answers into Lean-checked rewards. The model supplies an answer or a complete
> finite certificate; trusted code constructs the formal checking obligation.

A mathematical problem can be clear before its answer is known. We can specify
which integers are allowed, what condition they must satisfy, and what makes a
solution the least one. Can that specification supply a reinforcement-learning
reward without someone first computing and storing the correct answer?

For a restricted class of decidable problems, yes. MathCheck RL explores
**formal verification of bounded mathematical submissions against frozen,
environment-owned specifications, producing rewards without precomputed answer
keys**. The specification carries the ground truth. The checker determines
whether a proposed answer satisfies it.

This motivation is different from fixing an exact-string grader. Tools such as
[Math-Verify](https://github.com/huggingface/Math-Verify) already handle numeric
and symbolic equivalence. Representations such as `33` and `33.00` can denote
the same answer; nearby values require whatever exactness or tolerance the task
actually specifies. A capable answer comparator is useful when a reference
answer exists. This project asks how to build the reward from the problem's
contract instead.

The present implementation is small: integer evaluation, bounded sums, counts,
minima, and complete relations over bounded integer pairs. That narrow surface
lets us inspect what a reward means before asking whether optimizing it helps
a model learn.

## Follow one problem from statement to reward

Consider this task:

> Find the least integer x in the half-open interval [0, 30) such that
> x leaves remainder 2 when divided by 3 and remainder 1 when divided by 5.

The environment freezes the following object before the model responds:

```json
{
  "kind": "minimum",
  "expression": "x%3 == 2 and x%5 == 1",
  "start": 0,
  "stop": 30
}
```

There is no expected-answer field. The prompt renderer describes the same
object in prose and adds the submission schema. The model must return exactly
one fenced JSON object:

````text
```json
{"answer": 11}
```
````

Let P(x) denote the two congruence conditions. The mathematical obligation for a
candidate a is:

```text
0 ≤ a < 30
and P(a)
and, for every x in [0, 30), x < a implies not P(x).
```

The final clause matters. Both 11 and 26 satisfy P; only 11 is the least
solution in the interval. A checker that tests feasibility alone would reward
26 for answering a different question.

MathCheck Engine translates the restricted expression into Lean integer
arithmetic. Its trusted template defines a Boolean decision for the complete
obligation, including an enumeration of all smaller values in the declared
interval. A generated theorem is discharged with `native_decide`. The current
implementation wraps this Boolean in its shared finite checker template; it
does not ask the model to invent the statement or write the proof script.

| Submission | Meaning | Expected outcome on a healthy backend |
| --- | --- | --- |
| `{"answer": 11}` | Feasible and least | `checked_success`, reward 1 |
| `{"answer": 26}` | Feasible but not least | `mathematical_rejection`, reward 0 |
| `{"answer": 12}` | Fails the predicate | `mathematical_rejection`, reward 0 |
| `{"answer": 41}` | Outside the interval | `mathematical_rejection`, reward 0 |
| `{"answer": true}` | Violates the integer schema | `invalid_input`, reward 0 |

The values in this walkthrough explain the controls. They are not stored as a
reference answer in the task used for reward. The checker can compute the
entire finite result internally: answer-key-free describes the supervision
interface, not an algorithm that avoids solving the computation.

The same distinction appears in pair tasks. If the contract asks for every
pair satisfying a relation, checking each submitted pair establishes validity
but leaves completeness open. MathCheck's pair checker constructs the entire
relation over the declared rectangle and checks equality with the sorted,
duplicate-free submitted list, together with its claimed cardinality. Leaving
out a valid pair fails the contract even if every listed pair is valid.

## What is frozen, and what the model controls

The primary environment's unit of trust is a `SpecificationTask`: a prompt,
family, identifier, and immutable specification. Today a deterministic
procedural generator supplies count, sum, minimum, and pair-count tasks. The
prompt and checker input derive from that same object. Exact evaluation is
supported by the Engine and by directly constructed tasks.

The model controls only its candidate or certificate. It cannot submit a new
predicate, change the bounds, or add a convenient Lean theorem. A strict parser
requires one JSON fence and no surrounding commentary. Duplicate JSON keys,
extra fields, booleans used as integers, oversized inputs, and malformed pairs
are rejected. Pair lists must satisfy the canonical ordering and uniqueness
rules before checking.

This is an intentionally exact submission language. Rejecting `33.00` as a
JSON floating-point value here would be a schema decision, not evidence that
modern mathematical graders cannot recognize equivalent numbers. A richer
contract could admit other representations; it would need explicit parsing
and semantics.

The compatibility Verifiers API has a private column named `answer`. This
project uses it to carry serialized specification data, because the rubric
receives that column. It contains no expected candidate and is not rendered
into the prompt. Rows mark `contains_expected_answer: false` to make this
unusual interface inspectable.

Specification digests identify the exact encoded task. Generated train and
evaluation sets remove duplicates and exclude shared digests. This establishes
exact specification separation. It does not establish that different modular
problems require different strategies, that a public task was absent from
pretraining, or that a model generalizes beyond these families.

## Why Lean if Python can evaluate the specification?

Python can implement every current check. It can enumerate an interval,
compute a sum, reject a nonminimal solution, or compare complete pair lists.
Exhaustive coverage comes from the contract and its implementation. Lean is
not necessary to remove an answer key.

The reason to explore Lean is the assurance architecture. The checking
obligation has a typed formal representation, its definitions and bounds are
visible in a generated artifact, and its discharge takes place within Lean's
proof infrastructure. These are useful foundations for connecting future
certificate checks to formal mathematical definitions. They do not establish
that Lean is faster, cheaper, or more reliable than an independently tested
Python implementation of these small computations.

The analogy with code verification helps locate the claim. A program can be
checked against a specification using tests, an executable interpreter, an SMT
encoding, or a proof assistant. Which approach is appropriate depends on the
semantic connection to the program, the proposition established, and the
trusted machinery. Python can itself host a solver or proof checker. The
choice is about how evidence is produced and checked, rather than the surface
language alone.

MathCheck uses compiled decision procedures. In the pinned
[Lean 4.23.0 reference](https://lean-lang.org/doc/reference/4.23.0/Tactic-Proofs/Tactic-Reference/#native_decide),
`native_decide` evaluates a decidable proposition through native compilation
and relies on `Lean.ofReduceBool`. This expands the trusted base to include
Lean's compiler and native execution. The result is a formal claim discharged
by compiled computation, with that trust assumption; it is not kernel-only
reduction.

There are further trusted boundaries. Python parses and translates the
restricted expression language, and a template constructs the obligation.
This translator is tested, but it is not a formally verified compiler. The
specification author remains responsible for the intended mathematics. A
successful Lean check establishes the generated encoded claim under the
pipeline's assumptions; it does not establish that an arbitrary prose question
was faithfully translated.

An independent Python evaluator is therefore useful as a differential control.
Agreement on valid and deliberately invalid candidates, negative intermediate
values, division semantics, boundaries, leastness, and completeness can expose
implementation mistakes. Timing both backends can measure the cost of the
chosen architecture. Agreement is evidence, not a proof that both
implementations are correct.

## How this differs from theorem-proving RL

In a theorem-proving environment, the target statement is usually fixed and
the model supplies a proof. A reference proof is unnecessary because the
proof checker can validate another proof of that statement. MathCheck follows
the same contract-first principle while asking for a different artifact: an
answer or finite certificate.

The environment does generate and discharge a formal claim. Saying that it
performs no proving would obscure that fact. The narrower distinction is that
the policy does not synthesize Lean proofs. Trusted code instantiates the
frozen acceptance relation with the candidate and uses a decision procedure.

Answer-finding also complicates comparisons with proof-synthesis systems. The
[AlphaProof paper](https://www.nature.com/articles/s41586-025-09833-y)
describes injecting plausible answers when formalizing some answer-finding
problems. A fixed theorem and a fixed relation over possible answers are
related interfaces, but they are not interchangeable.

Learning without answer labels is an existing research direction.
[JURY-RL](https://arxiv.org/abs/2604.25419), a 2026 preprint, combines
rollout-derived answer proposals with a Lean proof pipeline and a fallback
when verification is inconclusive. MathCheck's current contribution is a
smaller engineering experiment: restricted, independently specified decidable
contracts connected to auditable reward verdicts. It does not claim to have
introduced label-free mathematical RL.

## A zero reward needs an explanation

The authoritative reward is binary: one for an accepted complete result, zero
otherwise. Formatting progress, partial pair lists, or reaching the compiler do
not receive positive reward. Diagnostic metrics carry that information with
zero weight.

| Status | Interpretation |
| --- | --- |
| `checked_success` | The encoded check completed and accepted |
| `mathematical_rejection` | A well-formed candidate failed the encoded check |
| `invalid_input` | Extraction or candidate validation failed |
| `unsupported_task` | Outside the implemented contract |
| `operational_error` | Toolchain, isolation, timeout, or process failure |

A missing compiler and an incorrect answer both receive zero during scoring,
but treating them as the same evaluation label makes an unhealthy worker look
like a weaker policy. Traces preserve status, stage, reason, timing, backend,
scope, specification and submission digests, invocation count, and diagnostic
messages. Operational failures remain visible in aggregate reports.

The native path requires an explicitly configured `lean-isolated` launcher and
Lean 4.23.0. It fails closed when required isolation is unavailable. It does
not silently substitute a host compiler. The wrapper limits individual
process resources; production service isolation and aggregate resource limits
would require further work.

Reward and metrics may be requested concurrently. They share one verification
result rather than compiling the same rollout twice. The v1 adapter uses an
event-loop-local single-flight cache keyed by exact input and runtime settings;
consumer cancellation does not cancel verification needed by other consumers.
Operational errors can be shared while in flight but are not retained as
completed cached verdicts, so a repaired backend can be tried again.

Process classification also has a limit: exit code 1 from the checker can
represent a Lean rejection or an otherwise unidentified failure. Timeouts,
wrapper failure codes, signals, and launch errors are explicitly operational.
Distinguishing every possible exit-1 infrastructure failure needs stronger
structured evidence from the checker process.

## Where specifications could come from

Procedural generation makes the initial fidelity problem manageable: the
specification comes first, and prose is rendered from it. An existing
natural-language dataset introduces another task: formalizing the question.
Dropping the answer column alone does not create a checker.

Each problem needs its own semantic instance, but it need not need a new
handwritten verifier. A reusable family can take parameters; a compositional
expression language can represent many instances; existing formal statements
can provide contracts. The present bounded DSL covers only a selected subset
of public math questions. Rational or real answers, geometry, symbolic answer
sets, and unbounded claims need additional contracts. Adding an arbitrary
finite search limit would change an unbounded problem rather than formalize it.

A future model-assisted pipeline could construct specifications from questions
in a separate context, blind to reference solutions and solver candidates. A
second reviewer could check quantities, units, domains, quantifiers, and the
objective; type checks and boundary mutations could reject malformed or
suspicious specifications. Only then would the environment freeze the
contract before the solving policy receives the task.

Different models or contexts can reduce direct leakage, but they do not
establish independent errors. Two formalizers can omit the same condition.
Compilation and provability cannot establish fidelity: a perfectly valid
theorem can express the wrong problem. Research such as
[Beyond Compilation](https://arxiv.org/abs/2606.31002) treats faithful statement
formalization as a separate evaluation target.

[Symbolic equivalence and semantic consistency](https://arxiv.org/abs/2410.20936)
are useful validation ideas, with limits. For answer-finding, compare the
acceptance relations over all admissible candidates, not merely whether two
closed claims are provable. Backtranslation, independent review, and human
calibration can catch errors that formal equivalence between two identically
mistaken specifications preserves. Report specification coverage and estimated
fidelity separately from solver success on accepted specifications.

An [offline GSM8K demonstration](docs/GSM8K_DEMONSTRATION.md) now accepts
question-only inputs and reviewed specifications, after the procedural
foundation. It includes four development tasks and one public test example;
its current review comes from the same assistant that constructed the specs,
so independent fidelity review remains outstanding. It has no native or
learning result. The known public test example illustrates the interface.
The official test split must remain evaluation-only if we want a held-out
measurement; public availability still leaves pretraining contamination open.
Questions from training can supply a separate development slice. Dataset
solutions can be consulted afterward for QA, but that must be disclosed and
kept separate from answer-blind construction and reward-time checking.

## What the evidence supports, and what comes next

The published RL 0.2.1 / Hub 0.1.1 release has preserved source tests, repeatable
wheel builds, installed-package checks, and isolated Lean positive and negative
controls. Exact artifacts and runtime boundaries are recorded in
[the release evidence](docs/RELEASE_EVIDENCE_0.2.1.md). A later source revision
needs its own live checks and release gate; passing tests with live integrations
skipped is not equivalent evidence.

A historical sequence-program run completed training steps and wrote a
checkpoint. It establishes that an earlier loop executed, not that the current
specification environment improves mathematical performance. The legacy
`native-verify-seq` adapter checks agreement with finite observations; it does
not prove a sequence rule for every natural number. Its evidence is kept
separate from the primary environment.

The primary environment is distributed on
[Prime Hub](https://app.primeintellect.ai/dashboard/environments/stanley-ngugi/mathcheck-rl).
Consumer installation and local setup were tested for the published version.
An authenticated hosted inference attempt stopped before a rollout because of
insufficient balance. Hosted model execution and learning gains remain
unestablished. [Reproducibility notes](docs/REPRODUCIBILITY.md) retain the
installation details and historical records without interrupting this argument.

The next empirical question is modest: can optimizing this reward improve
performance on different frozen instances of the implemented families? The
[procedural pilot](docs/M5_PILOT_PROTOCOL.md) defines paired pre/post evaluation,
a separate confirmatory split, family-balanced training, explicit policy
updates, and a feasible call allocation. Its revised protocol is a planning
artifact, not a completed experiment. Exact model, trainer, checkpoint and
runtime identities must be frozen, and native release checks and quota
availability must be established before execution.

The order matters: stabilize the current contract and instrument, check their
behavior, measure a bounded procedural pilot, then demonstrate a reviewed
dataset import. Larger autoformalization and richer mathematical contracts can
follow evidence rather than stand in for it.

MathCheck RL's useful claim is concrete: a model can submit ordinary answer data
and receive a mechanically checked reward against a complete formalized
contract, without a precomputed reference candidate. The difficult work moves
into specifying the right contract and preserving the evidence needed to
interpret each result. That is a tractable foundation for research, provided
we measure both parts honestly.

The code is public under the MIT license at
<https://github.com/stanleyngugi/mathcheck-rl>. The companion
[Engine article](https://stanleyngugi.netlify.app/posts/mathcheck-engine.html)
explains the generated checking artifacts in more detail.
