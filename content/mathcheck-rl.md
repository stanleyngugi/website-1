# Grading Mathematical Answers Without Answer Keys

> MathCheck RL turns frozen mathematical specifications into rewards for
> bounded answers and complete finite certificates. The model supplies data;
> trusted code constructs and executes the Lean checking obligation.

A mathematical problem can be clear before its answer is known. We can state
which integers are allowed, what condition they must satisfy, and what makes a
solution the least one. Can that statement supply a reward without someone
first computing and storing the correct answer?

For a restricted class of decidable problems, yes. MathCheck RL explores that
interface: **grade a candidate against an environment-owned specification,
without a precomputed reference answer**. Its current implementation covers
exact nonnegative integer answers for arithmetic evaluation, bounded sums,
counts and minima, together with complete relations over bounded integer pairs.

In reinforcement learning with verifiable rewards (RLVR), a checker scores
model outputs and those scores can guide policy updates. This project supplies
the task and reward layer. Whether training on that reward improves a model is
a separate empirical question; a training result is not required to demonstrate
the checking contract.

## What replaces the answer key?

A reference-answer grader compares a candidate `a` with a stored answer
`a*`. A specification grader asks whether `V(S, a)` holds, where `S` is
the frozen problem specification and `V` implements its acceptance relation.
For a minimum, that relation includes both feasibility and leastness. For a
complete enumeration, it includes both validity and completeness.

The specification supplies the rule for correctness. The checker still has to
decide whether the candidate meets that rule. In the current bounded families,
it can do this by computing the entire finite result. **Answer-key-free does
not mean computation-free, supervision-free, or necessarily cheaper than
solving the problem.** It means a reference candidate need not be prepared and
stored before scoring.

This motivation is different from repairing an exact-string grader.
[Math-Verify](https://github.com/huggingface/Math-Verify), for example, handles
numeric and symbolic equivalence against reference answers. `33` and
`33.00` can denote the same value; accepting nearby values depends on the
task's stated tolerance. A capable comparator is useful when a reference
answer exists. MathCheck asks how to obtain the reward from the contract itself.

A contract also costs work to construct. It must identify the right domain,
quantities, conditions and objective. Removing a stored answer does not remove
the need for trustworthy supervision; it moves that responsibility into the
specification and its checker.

## Follow one problem from statement to reward

Consider this task:

> Find the least integer x in the half-open interval [0, 30) such that
> x leaves remainder 2 when divided by 3 and remainder 1 when divided by 5.

“Half-open” means 0 is included and 30 is excluded. Before the model responds,
the environment freezes this specification:

```json
{
  "kind": "minimum",
  "expression": "x%3 == 2 and x%5 == 1",
  "start": 0,
  "stop": 30
}
```

There is no expected-answer field. The prompt renderer describes this object
and adds the required submission format. The model returns one fenced JSON
object:

````text
```json
{"answer": 11}
```
````

Let P(x) denote the two remainder conditions. For a candidate a, the complete
mathematical obligation is:

```text
0 ≤ a < 30
and P(a)
and, for every x in [0, 30), x < a implies not P(x).
```

The last clause is essential. Both 11 and 26 satisfy P; only 11 is least.
Checking P(26) alone would reward a feasible solution to a different question.

The responsibilities are divided as follows:

1. **MathCheck RL** owns the frozen task, renders the prompt and parses the
   candidate.
2. **MathCheck Engine** translates the restricted expression into Lean integer
   arithmetic and constructs the complete acceptance test.
3. **The isolated Lean runtime** evaluates the generated obligation using
   `native_decide`.
4. **The reward adapter** maps the verdict to a binary score and preserves
   diagnostic evidence.

Internally, the Engine defines a Boolean acceptance test and embeds it in a
shared finite checker template. The template compares a computed success
marker with 1; computing that marker includes the entire acceptance test,
rather than sampled checks of the domain. A theorem about this concrete
computation is discharged by compiled decision. The model supplies neither
the theorem statement nor a proof script.

| Submission payload | Meaning | Expected outcome on a healthy backend |
| --- | --- | --- |
| `{"answer": 11}` | Feasible and least | `checked_success`, reward 1 |
| `{"answer": 26}` | Feasible but not least | `mathematical_rejection`, reward 0 |
| `{"answer": 12}` | Fails the predicate | `mathematical_rejection`, reward 0 |
| `{"answer": 41}` | Outside the interval | `mathematical_rejection`, reward 0 |
| `{"answer": true}` | Violates the integer schema | `invalid_input`, reward 0 |

Each payload must appear inside the required JSON fence. These values explain
the acceptance rule; they are not stored as a reference answer in the task.
Expected outcomes are also different from evidence that a particular runtime
actually produced them.

The specification includes its bounds. Acceptance establishes leastness
inside [0, 30); it does not automatically establish an unbounded claim.

## A valid witness is not a complete result

The same issue appears when a problem asks for every pair satisfying a
relation. Consider integer pairs in [0, 5) × [0, 5), subject to:

```text
x < y and x + y = 4.
```

The satisfying relation is `[(0, 4), (1, 3)]`. A complete submission is:

```json
{"answer": 2, "pairs": [[0, 4], [1, 3]]}
```

Submitting only `[[0, 4]]` gives a valid witness, but omits another required
pair. Even a claimed count of 1 agrees with that incomplete list without
answering the original question.

MathCheck constructs the entire satisfying relation over the frozen rectangle,
checks exact equality with the submitted list, and checks its claimed
cardinality. Pairs must be sorted lexicographically and contain no duplicates.
This is a **complete finite certificate**: all required pairs within the
declared domain are present.

Here “certificate” does not imply a compact proof or a cheaper verification
algorithm. The checker recomputes the relation, and the certificate can grow
with its size. The benefit of this interface is an explicit completeness
obligation. It makes no statement about pairs outside the rectangle.

## The implemented contract

The current surface is deliberately small enough to inspect.

| Task | Model supplies | Acceptance requires |
| --- | --- | --- |
| Exact evaluation | Nonnegative integer | Equality with the encoded arithmetic expression |
| Bounded sum | Nonnegative integer | Equality with the sum over every declared index |
| Bounded count | Nonnegative integer | Equality with the number of satisfying indices |
| Bounded minimum | Nonnegative integer | Domain membership, predicate satisfaction and no smaller satisfying index |
| Bounded pair relation | Count and complete pair list | Exact relation equality and matching cardinality |

The expression language looks like Python arithmetic, but it is a restricted
language parsed and translated by trusted code, not arbitrary Python executed
with `eval`. It supports integer arithmetic, limited literal powers,
comparisons and Boolean operations. Division and modulo require a positive
literal divisor. `//` denotes integer floor division; rational division and
implicit rounding conventions are not part of the contract.

Indices and pair coordinates are nonnegative. Expressions can have negative
intermediate values, but the scalar submission schema admits only nonnegative
integers smaller than `10**1000`. A problem with a negative final result
therefore needs a different submission contract. Scalar search intervals
contain at most 10,000 indices; pair rectangles contain at most 10,000 points.
Expression-size limits and process resource limits further bound the workload.

A minimum task also needs a satisfying value if it is to have an accepted
integer answer. The procedural generator constructs satisfiable instances.
The current schema has no “no solution” certificate; an arbitrary predicate
with no solution cannot be answered successfully just by submitting an integer.

This scope excludes arbitrary real or rational answers, geometry, symbolic
solution sets and unbounded claims. A finite search limit is faithful only
when it is part of the problem or otherwise justified. Adding one to an
unbounded question changes the question.

The primary environment's task object, `SpecificationTask`, binds an
identifier, family, prompt and immutable specification. Its default generator
produces count, sum, minimum and pair tasks. Exact evaluation is supported by
the Engine and by directly constructed tasks, including the small dataset
demonstration.

The model controls only its answer data. It cannot replace the predicate,
change the bounds or submit a convenient theorem. Parsing requires exactly
one JSON fence with no surrounding commentary. Duplicate keys, extra fields,
booleans used as integers, malformed pairs and oversized inputs fail before
native checking.

Rejecting `33.00` as a JSON floating-point value here is a choice of submission
schema. It is not evidence that modern graders cannot recognize equivalent
numbers. Other representations would need explicit parsing and semantics.

The compatibility Verifiers API has a column named `answer`; MathCheck uses
it to carry serialized specifications because the rubric receives that column.
It stores no expected candidate, is not rendered into the prompt, and is
marked `contains_expected_answer: false`. The field name should not be
mistaken for an answer key.

## Why Lean if Python can evaluate the specification?

Python can implement every current check, including exhaustive enumeration,
leastness and complete-list equality. A carefully tested Python implementation
is a legitimate baseline. Removing an answer key does not require Lean.

The reason to explore Lean is the assurance architecture: a typed formal
representation of the obligation, inspectable definitions and bounds, and a
formal claim discharged within Lean's proof infrastructure. That is a basis
for connecting future certificate checks to mathematical definitions. It does
not establish a speed, cost or reliability advantage for these small tasks.

The analogy with code verification is useful. Tests, an executable semantic
model, an SMT solver and a proof assistant provide different ways to establish
a property. The important questions are what property is established, how the
encoding connects to the intended program or problem, and which machinery
must be trusted. Python can host a solver or proof checker too; the surface
language alone does not determine the strength of the evidence.

In the present implementation, the Engine constructs the formal acceptance
test and `native_decide` executes a decision procedure for it. The pinned
[Lean 4.23.0 reference](https://lean-lang.org/doc/reference/4.23.0/Tactic-Proofs/Tactic-Reference/#native_decide)
explains that native evaluation relies on `Lean.ofReduceBool`. This adds
the Lean compiler and native execution to the trusted base. The resulting
theorem is therefore not established by kernel-only reduction.

Other trusted components remain:

- **The specification author** chooses the intended domain and mathematical
  meaning.
- **The Python translator and source template** turn that specification and
  candidate into the Lean checking artifact.
- **The runner and reward adapter** execute the checker and interpret its
  outcome.

The translator is tested, but it is not a formally verified compiler. A
successful check establishes the generated encoded claim under these
assumptions. It does not establish that an arbitrary prose question was
faithfully translated.

An independent Python evaluator is useful precisely because it exercises
another implementation of the contract. Differential controls compare valid
and deliberately invalid candidates, boundary values, negative intermediate
arithmetic, division, leastness and completeness. Agreement can expose bugs
and timing can reveal overhead. Agreement is evidence, not a proof that both
implementations are correct.

## How this relates to theorem-proving RL

In a typical theorem-proving environment, the statement is fixed and the model
supplies a proof. A reference proof is unnecessary: the proof checker can
validate a different proof of the same statement.

MathCheck follows the same contract-first principle, while asking the policy
for an answer or a complete finite certificate. Trusted code instantiates
the acceptance relation with that submission and discharges the resulting
claim by a decision procedure. Formal proving occurs in the pipeline; the
policy does not synthesize Lean proofs.

Answer-finding needs care in this comparison. A statement that 11 satisfies
a predicate is weaker than a statement that 11 is the least solution. The
[AlphaProof paper](https://www.nature.com/articles/s41586-025-09833-y)
also describes gathering plausible answers for some answer-finding problems
and injecting them during formalization. A fixed theorem and a fixed relation
over candidate answers are related interfaces, but their obligations must be
spelled out.

Label-free mathematical RL is already a research direction.
[JURY-RL](https://arxiv.org/abs/2604.25419), a 2026 preprint, combines
rollout-derived answer proposals with formal verification and a fallback
reward when verification is inconclusive. MathCheck's present contribution
is a smaller engineering demonstration: bounded, environment-owned contracts
connected to explicit reward verdicts. It does not claim to have introduced
learning without answer labels.

## A zero reward needs an explanation

The authoritative reward is 1 for an accepted complete result and 0 otherwise.
Partial pair lists, formatting progress and reaching the compiler receive no
positive reward. Diagnostic metrics have zero weight.

| Status | Interpretation |
| --- | --- |
| `checked_success` | The encoded check completed and accepted |
| `mathematical_rejection` | The checker reported rejection of a well-formed candidate |
| `invalid_input` | Extraction or candidate validation failed |
| `unsupported_task` | The request is outside the implemented contract |
| `operational_error` | Toolchain, isolation, timeout or process failure |

This is the vocabulary of the verdict layer; individual entry points may
reject unsupported specifications during construction instead of scoring them.

An incorrect answer and a missing compiler both deny reward. They should not
be interpreted as the same experimental outcome: an unhealthy worker is not
evidence of a weaker policy. Traces retain status, stage, reason, timing,
backend, scope, specification and submission digests, invocation count and
diagnostics. Evaluation should report operational failures separately.

Exit code 1 alone does not establish a mathematical rejection. Current candidate
source requires the complete recognized `native_decide` diagnostic that its
proposition evaluated to false. Unrecognized, truncated or mixed error output,
timeouts, wrapper failure codes, signals and launch errors are operational.
This is conservative interpretation of trusted checker diagnostics, not an
exported mathematical counterexample. A changed diagnostic format can require
an adapter update; the current candidate still needs its live validation gate.

The native path requires Lean 4.23.0 and an explicitly configured
`lean-isolated` launcher. Missing isolation fails closed, with no silent host
compiler or Python-reward fallback. Per-process limits do not constitute a
complete production service isolation design.

The adapters also avoid compiling the same rollout twice when reward and
metrics are requested concurrently. They share an exact-input verification
result, accounting for runtime settings. Consumer cancellation does not cancel
work still needed by another consumer. Operational failures are not retained
as completed cached verdicts, allowing a repaired backend to be tried again.
These are execution properties, separate from the mathematical contract.

## Where specifications come from

Procedural generation makes the first specification problem manageable:
construct the contract first, then render the prompt from it. This avoids a
separate open-ended prose formalization step, although the renderer and checker
still need review.

An existing math dataset reverses that direction. The question arrives in
prose; someone must construct its semantic specification. Dropping the answer
column alone does not produce a checker.

Every question needs a semantic instance, but not necessarily a new handwritten
verifier. A family can reuse a checker with different parameters, and a
compositional expression language can encode many arithmetic instances. What
cannot be reused blindly is the interpretation of the question.

For example, “earn $12 per hour for 50 minutes” can be encoded as:

```text
(12 * 50) // 60
```

The units explain the expression: dollars per hour times minutes, divided by
60 minutes per hour. This particular division is exact. If it were not, floor
division would impose a rounding rule that needs justification. The
specification stores the computation, rather than its evaluated answer.

The [question-only GSM8K demonstration](docs/GSM8K_DEMONSTRATION.md) freezes
three admitted development contracts from five selected training questions,
records two exclusions, and includes one already known public-test example.
One exclusion counts friends without stating how many clips each friend
bought; another leaves a year-to-weeks convention unstated. These exclusions
illustrate a deliberate admission policy, not a claim that the original
dataset has no intended answers.

The questions are tied to upstream provenance. Solution fields are discarded
before formalization and are absent from the imported artifacts. The same
assistant context constructed and reviewed the contracts, as disclosed in
the [semantic audit](docs/GSM8K_SPEC_AUDIT.md). That is not independent review,
and answer-blind inputs do not establish that a public question or answer was
absent from model pretraining. The demonstration has Python-only controls,
but no completed current native or policy evaluation.

The known public-test example demonstrates the interface; it is not a fresh
held-out measurement. For a future study, use training questions for policy
updates, reserve a development subset for design choices, and keep test
questions evaluation-only. Repeatedly using test feedback to revise contracts
or prompts compromises their role as held-out data. Dataset solutions consulted
later for QA must be disclosed separately from answer-blind construction and
reward-time checking. [Dataset-role notes](docs/DATASET_ROLES.md) describe
possible sources and their contract limitations.

Generated procedural splits remove duplicates and exclude shared specification
digests. A digest identifies an exact encoded task. Digest separation does
not establish semantic independence between similar problems, absence from
pretraining, or generalization beyond the implemented families.

## Could a separate model construct the specifications?

A future model-assisted pipeline could produce a specification in a context
separate from the solving policy, without reference solutions or candidate
rollouts. Review would then check quantities, units, domains, quantifiers and
the objective; compilation and mutation controls could detect some errors.
Only an admitted contract would be frozen and passed to the solver.

That pipeline is not currently automated. A different model or context can
reduce direct leakage, but two formalizers can still omit the same condition.
Compilation establishes that an encoding is well formed; proving a claim
about it does not establish that it expresses the question.

[Beyond Compilation](https://arxiv.org/abs/2606.31002) studies this gap between
Lean compilation and faithful statement formalization.
[Symbolic equivalence and semantic consistency](https://arxiv.org/abs/2410.20936)
offer complementary validation ideas. For answer-finding, equivalence should
concern the acceptance relations across admissible candidates, rather than
just whether two particular closed claims are provable.

Even equivalent encodings can share the same mistaken interpretation.
Backtranslation, independent review and human calibration address another
part of the problem. A study should report specification coverage and fidelity
separately from solver success on admitted contracts. Unsupported or
unfaithful formalization is not simply a wrong solver answer.

## What has actually been demonstrated?

The current source candidate and the older published release have different
evidence. Their records should not be combined into a claim that the latest
code passed native validation.

| Record | What it supports | Boundary |
| --- | --- | --- |
| Published RL 0.2.1 / Hub 0.1.1 | Preserved source tests, repeatable wheel builds, consumer installation and isolated Lean acceptance/rejection controls | Evidence for those historical artifacts |
| Current integration candidate, recorded 2026-10-03 | 178 RL tests; 85 Engine tests plus 40 subtests; four wheel builds; fresh dependency and installed-package checks | 14 RL and 10 Engine live/platform skips; native validation blocked |
| Optional trainer smoke | Actual gradient updates, frozen-reference integrity and a tiny checkpoint round trip | Random model fixture, not mathematical learning evidence |

The [current validation record](docs/CURRENT_VALIDATION.md) links the logs
and [integration closeout report](docs/evidence/engine-integration-20261003/closeout.json). Candidate versions
are Engine 0.3.3, RL core/sequence 0.2.2 and Hub 0.1.2; they have not replaced
the public releases. The available execution surface lacks the `/proc` access
needed by stock Lean and bubblewrap. Installing the official toolchain did
not resolve that environment limitation. The closeout command correctly
reports source delivery complete, native validation blocked and release
readiness false.

The earlier [release evidence](docs/RELEASE_EVIDENCE_0.2.1.md) remains available.
The public [Prime Hub environment](https://app.primeintellect.ai/dashboard/environments/stanley-ngugi/mathcheck-rl)
has recorded consumer installation and local setup evidence. A hosted
inference attempt stopped before a rollout because of insufficient balance;
no hosted model execution is inferred from successful installation.

A historical sequence-program run completed training steps and wrote a
checkpoint. That was a different contract: the legacy `native-verify-seq`
adapter checks agreement with finite observations. It does not establish a
sequence rule for every natural number, or a learning gain for the current
specification environment. [Reproducibility notes](docs/REPRODUCIBILITY.md)
preserve that history separately.

## A finite delivery and an optional learning experiment

The [finish line](docs/FINISH_LINE.md) requires explicit contracts, source
checks, reproducible installed packages, honest writing, the disclosed small
dataset demonstration and current native checking evidence. Source delivery
is complete. One required validation gate remains: execute the existing
closeout command on supported Linux and pass its live suites, native controls
and installed-wheel release gate.

An RL training run is not part of that completion requirement. The
[optional procedural pilot](docs/M5_PILOT_PROTOCOL.md) and
[local trainer](docs/LOCAL_TRAINING.md) are implemented for a separately
requested experiment. They ask a modest further question: can optimizing this
reward improve performance on different frozen instances of these families?
The protocol defines paired evaluation and a separate confirmatory split;
no pretrained-policy pilot or learning gain has been demonstrated.

Broader mathematical contracts, automatic formalization and larger dataset
studies are separate projects. They should not keep this bounded delivery open.

MathCheck RL demonstrates a concrete separation of responsibilities: the
environment owns the question's encoded contract, the model supplies answer
data, and the checker produces an interpretable reward without a stored
reference candidate. The hard work remains specifying the right contract
and preserving evidence for what each verdict means. That boundary is the
foundation of the project.

The code is public under the MIT license at
<https://github.com/stanleyngugi/mathcheck-rl>. The companion
[Engine article](https://github.com/stanleyngugi/mathcheck-engine/blob/main/TECHNICAL_ARTICLE.md)
explains the generated checking artifacts in more detail.
