# Grading Mathematical Answers Without Precomputed Answer Keys

MathCheck RL leverages a frozen mathematical specification to reward bounded answers and complete finite certificates for mathematical problems. The model generates the data and trusted code constructs and executes the corresponding checking obligation in Lean.

Can we obtain a reward function for a mathematical problem without computing and storing the answer somewhere?

For a restricted class of decidable mathematical problems, MathCheck RL demonstrates that this is possible. More precisely, MathCheck RL shows how to implement an interface that, given a specification for a problem owned by the environment, rewards answers to it without relying on a precomputed reference answer. The current implementation covers problems whose answer is a non-negative integer and which can be specified exactly by (1) evaluating an arithmetical expression, or (2) summing up, counting, or minimising over bounded quantities. It also covers (3) a complete relation over pairs of bounded integers, submitted as a count and a full pair list.

As with other RLVR work, the task and reward are provided but it remains an empirical question to investigate how well these rewards work for training.

Instead of comparing a generated answer `a` to a reference answer `a*`, the idea is to compare it to the specification of the problem: does `V(S, a)` , where S is some frozen representation of the problem specification, and V is some implementation of the "acceptance" relation for S , which would include both feasibility and leastness in the case of minimum, for instance, or both validity and completeness in the case of enumeration of all valid objects.

The specification tells what it means for a generated answer to be correct, but there is still a question of checking this. The current family of specifications is set up so that this can be done by computing the whole result, but the whole result is necessarily finite. The approach is answer key free, but not necessarily computation free, supervision free, or cheaper than just solving the problem. The point is to not need to prepare and store answer candidates in advance.

This is a somewhat different motivation from the one behind e.g. the work on relaxing exact string match in graders. There is work on this, e.g. [Math-Verify](https://github.com/huggingface/Math-Verify) , which aims to deal with cases like the provided answer being 33 and the reference answer being 33.00 . (Whether answers close to the reference one should be accepted will depend on the task.) This is useful, but assumes one has reference answers. MathCheck is motivated by: how does one get the reward signal directly from the contract?

This is not free, as constructing the contract is work.


## Here's an example of how MathCheck works

Find the least x in [0, 30) such that x % 3 == 2 and x % 5 == 1 (here, [0, 30) is half-open, meaning 0 is included but 30 is excluded).

MathCheck RL serializes the task specification (which has been frozen at this point) into a JSON blob, which looks like:

```json
{ "kind": "minimum", "expression": "x%3 == 2 and x%5 == 1", "start": 0, "stop": 30 }
```

Note that there is no expected answer. This specification is passed to the prompt renderer, which turns it into a natural language description of the task along with instructions on how the model should format its submission. The model should produce exactly one JSON object, surrounded by a code fence, like:

````text
```json
{"answer": 11}
```
````

Now, MathCheck Engine turns the expression into Lean code that operates over integers, and constructs the full acceptance test:

```text
0 <= a < 30 and (a % 3 == 2 and a % 5 == 1) and forall x in [0, 30), x < a -> not (x%3 == 2 and x%5 == 1)
```

Note that the expression x%3 == 2 and x%5 == 1 has two solutions in [0, 30) (namely 11 and 26) so the extra conjunct is needed to ensure that the model found the least.

At this point, the work is distributed as follows:

MathCheck RL is responsible for (a) the task specification, which is frozen, (b) rendering the task into a prompt for the model, and (c) parsing the model's submission.

MathCheck Engine is responsible for turning the restricted expression into a piece of Lean code that operates over the integers, and assembling the acceptance test.

The runtime, running in an isolated context, is responsible for evaluating the acceptance test using native_decide .

The reward function adapter is responsible for turning the result into a binary reward, along with evidence.

MathCheck Engine turns this into a boolean acceptance test and plugs it into a shared template for finite checkers, resulting in a statement of the form computed_test =? 1 = 1 where the term computed_test involves a computation that includes the entire acceptance test. A theorem asserting this statement is then proved using native_decide , which compiles down the decision procedure. Note that the model is not asked to state or prove a theorem!

|Submission payload|Meaning|Expected outcome on a healthy backend|
|---|---|---|
|`{"answer": 11}`|Feasible and least|`checked_success`, reward 1|
|`{"answer": 26}`|Feasible but not least|`mathematical_rejection`, reward 0|
|`{"answer": 12}`|Fails the predicate|`mathematical_rejection`, reward 0|
|`{"answer": 41}`|Outside the interval|`mathematical_rejection`, reward 0|
|`{"answer": true}`|Violates the integer schema|`invalid_input`, reward 0|

Each payload must be enclosed in exactly one `json` code fence, with no commentary and only the required fields.

Note that the values in the payload above are only for illustrating the acceptance rule of this problem. They are not stored as the task’s reference answer. The expected verdicts shown here should also not be mistaken for evidence of an actual checker execution.

Note that the above acceptance rule only shows that the answer is the least element in the range [0, 30). It does not show it is the least element without range restriction.

## Problem with valid witness but not the correct answer

Consider the following problem, where the goal is to find all integer pairs from the Cartesian product [0, 5) × [0, 5) that satisfy the following relation:

```text
x < y and x + y is equal to 4
```

For this example, the answer satisfying the relation is [(0, 4), (1, 3)]. A complete answer should be given in the following format:

```json
{"answer": 2, "pairs": [[0, 4], [1, 3]]}
```

Notice that if only one of the pairs, e.g., [[0, 4]], is given in the answer payload, it is a valid witness but not a complete answer. The same goes for answering the number of pairs: even though there is no contradiction in the answer by claiming that there is only one pair (i.e., answer = 1) that satisfies the relation and listing one such pair, the answer is not correct.

To be accepted by MathCheck, (1) the entire relation that satisfies the property over the frozen rectangular domain will be constructed, (2) the list of pairs in the answer must be exactly equal to the constructed relation and (3) the number of pairs in the answer must be exactly equal to the cardinality of the constructed relation. Note that the order of pairs in the answer must be lexicographically sorted and there can not be any duplicate pairs. By doing so, the answer will be a complete finite certificate for the problem.

Here, “certificate” does not necessarily mean a succinct and computationally inexpensive proof. The checker still needs to (re-)construct the relation. The benefit of the answer interface is that it requires the answer to be complete (w.r.t. the given rectangular domain). Beyond the rectangular domain, no statement is made.

## The implemented contract

The reason it is this small is because right now it is supposed to be small enough to inspect.

| What the task asks for | What is required for acceptance? |
| --- | --- |
| to exactly evaluate some arithmetic expression | submit a nonnegative integer that equals the encoding of the arithmetic expression |
| to evaluate the sum of some arithmetic expression within some index bounds | submit a nonnegative integer equal to the sum for all indices in the bounds |
| to evaluate the count of indices within some index bounds satisfying a predicate | submit a nonnegative integer equal to the count of indices in the bounds satisfying the predicate |
| to find the minimum index within some index bounds satisfying a predicate | submit an integer that is within the index bounds, that satisfies the predicate, and that is less than or equal to all other indices that satisfy the predicate |
| to find the set of pairs within some pair bounds satisfying a relation | submit the count and an enumeration of all pairs (x,y) in the pair bounds that satisfy the relation, and the number of such pairs is equal to the submitted count |

The expressions are meant to represent something like what could be written in Python for arithmetic expressions. They are not evaluated with Python's eval but are instead parsed and translated by some trusted code. The language supports arithmetic on integers, raising integers to some powers of literals, comparisons, and boolean operations. Division and modulo by positive literals is supported, as is integer floor division with //. Division of rationals and implicit rounding is not supported (yet?).

Indices and pair coordinates must be nonnegative. Negative values can exist within expressions, but the schema for the submission of scalar values only allows nonnegative integers less than 10**1000. If a problem requires a negative number as an answer then a different submission schema will be needed. The maximum number of indices for searching for a scalar value is 10,000. The maximum number of points in a rectangle when searching for pairs is 10,000. There are also limits on the allowed sizes of expressions and on the resources of the process that does the evaluation.

For minimum tasks, a satisfying value must exist. The problem is procedurally generated in a way that guarantees this. There is currently no way to submit a 'no solution' certificate. For a bounded predicate, nonexistence could in principle be checked exhaustively, but the current submission schema requires a satisfying integer.

The current scope of problems does not include arbitrarily precise real or rational numbers as answers, geometry, returning a symbolic expression that represents a set of solutions, or anything unbounded. Adding something like a finite limit to a problem that doesn't have one is not a faithful representation of the problem unless the problem itself implies such a limit. Asking someone to find a solution to something and then adding 1 to the question changes the question.

To evaluate an answer exactly, the simplest way is to use one of the tasks from the primary environment, whose task object is called `SpecificationTask`. It binds together an id, family, prompt, and an immutable specification, and the default generator will produce count/sum/min/pair tasks. These can be evaluated exactly using the Engine , or by constructing the task directly as demonstrated in the [small dataset](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/GSM8K_DEMONSTRATION.md).

When training a model for this environment, the only degree of freedom is the data sent in the answer field. It won't help, for example, to replace the predicate or change the bounds, because those are given in the task specification which the model can't change. Nor does it help to "submit a theorem" in the hopes that the grader will prove it for the model. The answer must contain exactly one JSON fence and no commentary. Some likely failure modes, which are checked in native code before even attempting to parse the JSON, include submitting a JSON object with duplicate keys, extra fields, booleans where an int is expected, ill-formed pairs, or inputs that are too large.

It may seem arbitrary that 33.00 is rejected as a JSON float, but this is only because it needs to conform to the submission schema; it has nothing to do with modern graders. Other ways of representing the same number would need to be parsed and given semantics explicitly.

To be compatible with the Verifiers API, MathCheck serializes the specification in the column called `answer`, because that's what the rubric expects. However, this column does not contain the expected answer for a candidate submission, and it is not rendered in the prompt. If interfacing with MathCheck through the Verifiers API, the answer column should be marked with `contains_expected_answer: false`.

## Why bother with Lean at all, when the spec is evaluable in Python?

It's true that all of the current checks can be implemented in Python. Even something like "exhaustively enumerate a space and return the elements satisfying a predicate, in any order" can be checked by exhaustively enumerating in Python, sorting, and checking equality. Things like "prove leastness" can be implemented by exhaustive enumeration, too. And of course, Python is a perfectly serviceable language for establishing a baseline for how well a model can do at these tasks before answer keys were removed.

The reason to even explore an approach involving Lean at all is that it makes an assurance architecture possible. Not only are the definitions and bounds passed as a formally-typed data structure, but the obligation itself is a formal statement in Lean that can be discharged using Lean's infrastructure.

The code verification analogy is interesting. When verifying code, one might employ a range of techniques like tests, an executable semantic model, an smt solver, or even a proof assistant. The key questions are what are the properties being proven and what machinery do these encodings use and how much of it needs to be trusted? There is no reason this machinery cannot be written in python.

Looking at the code, the Engine is constructing a test for acceptance and then using native_decide to run a decision procedure on it. According to the [Lean reference (v4.23.0)](https://lean-lang.org/doc/reference/4.23.0/Tactic-Proofs/Tactic-Reference/#native_decide) (pinned version in the environment), this would use `Lean.ofReduceBool`, which as the name suggests brings the lean compiler and native execution into the trusted base.

Additionally, the following need to be trusted:

- The author of the specification (domain and math knowledge)

- The python code that translates the specification and candidate into the lean checking artifact (source template)

- The runner and reward adapter that runs the checking artifact

The translator is tested but not a formally verified compiler. Hence the theorem being proved is really that the encoded claim is true under a number of assumptions. Note that this approach is not general as it would need to translate an arbitrary question into a form that can be checked.

There is also an evaluator written in python that can be run separately. This provides differential style controls and can be used to confirm that the implementation broadly matches the contract by trying valid and invalid candidates. It also allows one to probe boundary conditions, like whether negative numbers in the intermediate arithmetic, division, leastness, and completeness are handled. Additionally, one can check whether the implementations agree and what the timing overhead is. Note that while this can help find bugs and show that the two agree it does not prove the implementations are correct.

## Similar to reinforcement learning for theorem proving?

Typically in theorem proving the theorem is fixed and the model only needs to provide the proof. So there's no need for a "reference proof", the proof checker can accept any proof of that theorem.

MathCheck does follow the contract-first approach; the policy model is asked to provide an answer or full finite certificate, and then trusted code instantiates the acceptance relation with that and discharges it by decision procedure. (So there is formal proving happening, just not proof synthesis in Lean by the policy model.)

The main thing that's different wrt answer finding is that the statement won't just assert that e.g. 11 is a solution, but that it's the least one. (Although even with just the weaker form, the [AlphaProof paper](https://www.nature.com/articles/s41586-025-09833-y) reports gathering a bunch of answers to inject during formalization for some answer-finding problems.)

And yeah, doing RL on math without using labels is definitely something that others are exploring too, e.g. the very recent (2026!) preprint [JURY-RL](https://arxiv.org/abs/2604.25419) has a similar approach of using rollouts to get answer proposals, and if formal verification of a candidate is not conclusive then it falls back to another way of computing a reward. MathCheck's novelty is pretty small and engineering-y, it's just an example of doing things the bounded way by having the environment own the contracts and emit reward verdicts.

## Re: Why the reward is always 0?

The authoritative reward signal is the last one and it is indeed 1 if the final result is accepted and 0 otherwise. The partial results reported as lists of pairs along the way, as well as the diagnostics about format progress and whether the code reached the compiler, don't contribute positively to the reward (they all have weight 0).

| Status | Interpretation |
| --- | --- |
| `checked_success` | The encoded check completed and accepted |
| `mathematical_rejection` | The checker reported rejection of a well-formed candidate |
| `invalid_input` | Extraction or candidate validation failed |
| `unsupported_task` | The request is outside the implemented contract |
| `operational_error` | Toolchain, isolation, timeout or process failure |

These are the vocabulary words of this layer. Note that some of these entry points may reject certain specs during their construction rather than returning scores for them.

Incorrect answers and a missing compiler both deny reward, but they are not equivalent from an experimental standpoint. Not considering unhealthy workers as a weaker policy is something that should be captured in traces, and this is why traces include all of their status, stage, reason, timing, backend, scope, spec digest, submission digest, invocation count, and diagnostic information. How to report all that in a digestible way is left to the evaluator, but the expectation is that any operational failures are separately reported.

Engine 0.3.3 is conservative in its interpretation of checker diagnostics and requires the entire set of native_decide diagnostics that it recognizes to conclude that a proposition mathematically evaluated to false. Anything else, including exit code 1 without those diagnostics, unrecognized diagnostics, mixed error output, timeouts, wrapper failure exit codes, signals, or wrapper launch errors are all treated as operational failures and not exported as mathematically sound counterexamples. This has the downside that any change in the format of diagnostics from a trusted checker will require an adapter update, but the released implementation does correctly pass the current live validation gate for lean 4.23.0.

Using this path requires lean 4.23.0 to be installed and the lean-isolated process launcher to be explicitly set. If process isolation cannot be configured then this adapter will fail closed and neither silently fallback to running the lean compiler in the host process nor to the python reward fallback. This does not represent a complete isolation design for production services, only some per-process limits.

Some implementation details of the current adapter releases: they do avoid double compiling for concurrent reward and metrics requests of the same rollout by sharing the exact same verification result for the same inputs (accounting for settings that may impact runtime), they do not shutdown in progress work when one consumer cancels their request if another consumer still needs the work, and they do not cache operational failures as completed so that operational issues can be resolved and the backend retried. These details are not part of the mathematical contract and are more just notes about the execution of the current adapters.

## Spec Sources

A nice property of procedurally generated specs is that the first step of generating a spec is to generate the procedural problem, which is essentially constructing the spec contract. This means that rendering the spec prompt doesn't require any open-ended formalization, though one should still inspect the renderer and check it.

There does exist a dataset like this, but it goes in the other direction: given a question (in prose) it’s asking to create a semantic specification. Ignore the answer column.

The difficulty is that each question requires its own semantic instance. While one can certainly define parameterized families of semantic checkers, and the expression language is sufficiently composable that it can capture a wide variety of arithmetic semantic instances, the semantic interpretation still cannot be reused.

For example, consider the question “If Sam can earn $12 per hour, how much money would he make if he worked for 50 minutes?” One semantic interpretation is (in Python):

```python
(12 * 50) // 60 # $/hr * min / (min/hr) = $
```

(Note: the division here is exact, but in general one would need to argue for the floor.) The semantic specification stored in the database is the above, not its evaluation.

For an example of this in action, consider the demo using only the questions from the [GSM8K dataset](https://github.com/openai/grade-school-math). Of the five questions selected for training (on which contracts are frozen), three were admitted (see [GSM8K demonstration](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/GSM8K_DEMONSTRATION.md)), and two were excluded due to being overly vague in the source dataset (e.g. a question about how many friends someone had, where it wasn’t stated how many clips each friend bought; or a question where the conversion from years to weeks was not specified according to any reasonable convention). The remaining question was already known, as it was in the public test set.

These questions may be sourced from the same upstream provenance, and because their solution fields are discarded prior to formalization, those solutions are not present in the imported artifacts. A single assistant context was used to both construct and review the contracts; this process therefore lacks independence. Furthermore, the answer-blind nature of the contract construction context does not ensure that the questions or answers appearing in the public dataset were not already part of the model's pretraining corpus. Native gate closeout is complete: all eight differential control evaluations (py/lean) for the three development contracts and one public test example have been completed and agree with no operational errors. See the [evaluation details](https://github.com/stanleyngugi/mathcheck-rl/tree/main/docs/evidence/native-closeout-whpx-20261005-final). These controls attest to the operation of the checkers on one correct and one nearby incorrect candidate answer per contract, but they do not measure policy performance, nor do they provide independent evidence of spec fidelity. For further details see the [semantic audit](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/GSM8K_SPEC_AUDIT.md).

The public test example is known and was used for interface demonstration. In a future investigation, the training set questions would be used for policy updates, a subset of the development set would be used to inform design choices, and the test set questions would be used for evaluation only. Repeated use of test set feedback to guide contract or prompt changes should be avoided. A separate disclosure is required to indicate which portions of the dataset were used to inform question answering. See the [dataset-role notes](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/DATASET_ROLES.md) for additional notes on potential dataset sources and contract-specific restrictions.

Procedurally generated splits were de-duplicated and separated on the basis of differing specification digests. This separation criterion does not imply semantic independence, absence from pretraining corpora, or generalization beyond implemented problem families.

## Could the specs have been constructed by a different model?

In future iterations, it would be possible to use a different model to construct specs in a separate context, without reference solutions or rollouts. This contract construction process could employ a variety of checks (e.g. semantic review of e.g. quantities, units, domains, quantifiers, objective, etc.; compilation; mutation controls, etc.) to ensure validity before admitting the spec into the frozen corpus for a solving policy.

Currently this isn't an automated part of the pipeline. While changing the model or adding context can reduce this problem, it's always possible for both formalizers to simply forget to encode a certain condition. Note that compilation only shows that the encoding is well formed, not that it is what it says it is.

See [Beyond Compilation](https://arxiv.org/abs/2606.31002) for further details on the gap between compiling in Lean and formally proving that the statement is correctly formalized. Some ideas for how to close this gap are in the work on [symbolic equivalence and semantic consistency](https://arxiv.org/abs/2410.20936). The reference equivalence there is for provability of closed claims, and in the context of finding answers to questions, would need to be adapted for different "admissible" answer candidates being accepted.

None of this avoids the problem of both encodings being wrong in the same way. Backtranslation, independent review, and human calibration are all good ideas. When reporting on studies, it's good to report specification coverage and fidelity separately from "success" of finding answers to admitted formal contracts, since a formalization can be not supported or not faithful to the specification, as well as the solver giving a "wrong" answer.

## What works?

Current releases include native work that has been validated and published. Note that validating the evidence is not the same thing as learning the evidence in a reward pipeline.

|What |How |Not |
| --- | --- | --- |
|Joint native gate (2026-10-05) |96 Engine tests and 52 subtests, 182 RL tests, isolated native tests as controls, python/lean differentials, repeatable build of all 4 wheels, and fresh checks of the installed packages |Skipping any native tests (PyTorch training module is optional) |
|Publish Engine 0.3.3, RL 0.2.2, Hub 0.1.2 |Hashes of downloaded artifacts, immutable pins for all dependencies, fresh install of consumers on both Windows and Linux, and accept/reject of installed consumers in isolation for Linux |Running the policy on the hosted machine or learning anything |
|Smoke test optional trainer |Gradient updates, frozen reference integrity, tiny model checkpoint round trip |Learning anything (fixtured with random model) |

The original gate (unchanged) now passes on Ubuntu 24.04.4 via QEMU WHPX (Python 3.12.3, bubblewrap 0.9.0, stock read-only Lean 4.23.0): exit 0 after 801.238 s, native validation complete and release_ready=true. Full evidence (exact source revisions, toolchain provenance, commands, complete logs, and artifact hashes) is in [closeout evidence](https://github.com/stanleyngugi/mathcheck-rl/tree/main/docs/evidence/native-closeout-whpx-20261005-final).

Published artifacts: [Engine v0.3.3](https://github.com/stanleyngugi/mathcheck-engine/releases/tag/v0.3.3), [RL core/sequence v0.2.2](https://github.com/stanleyngugi/mathcheck-rl/releases/tag/v0.2.2), and a public [Prime Hub environment (Prime)](https://app.primeintellect.ai/dashboard/environments/stanley-ngugi/mathcheck-rl) at version **0.1.2**. Prime rebuilt the wheel (archive hash differs from the locally validated wheel), but packaged environment code matches after line-ending normalization and dependency pins for mathcheck-engine and mathcheck-rl-core are unchanged; installation in a fresh Linux consumer passes `pip check` and all six isolated native controls (no checker invoked on invalid input). Publication record and installed-consumer results are in [publication.json](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/evidence/native-closeout-whpx-20261005-final/publication.json).

Note: the current [validation record](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/CURRENT_VALIDATION.md#final-native-closeout--2026-10-05) preserves earlier blocked validation attempts for historical context, but the passing native gate and the publication records above supersede that prior pending status. (Earlier evidence for v0.2.1 remains at [RELEASE_EVIDENCE_0.2.1.md](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/RELEASE_EVIDENCE_0.2.1.md).) The historical hosted inference was never executed due to insufficient balance.

The prior run of the sequence program is historical: it completed training steps and produced a checkpoint, but only satisfied the legacy `native-verify-seq` adapter (agreement on a finite set of observations). It did not establish a rule for all natural numbers nor demonstrate learning under the current specification environment. See [reproducibility notes](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/REPRODUCIBILITY.md).

For the Finish Line to be completed, the requirement was to ensure contracts are explicit, the source of the contract can be checked, that the packages were installed from the source and that the work was done in an honest way by providing evidence (showing that the dataset used was a demo dataset and current working native). The task is complete, Linux gate still passes with no change, new releases are created on GitHub and the package on the Hub. Check using the new consumers to see that the packages are installed correctly. See the [finish line](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/FINISH_LINE.md).

Note: the task was completed without training the agent using Reinforcement learning. However, the experiment was specifically requested to see if training on optimizing the reward improves the performance on a different instance of the same families of contract, but frozen. As such, the implementation can be found in the [M5 Pilot Protocol](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/M5_PILOT_PROTOCOL.md) and [Local Training](https://github.com/stanleyngugi/mathcheck-rl/blob/main/docs/LOCAL_TRAINING.md) , however, this was not required to be done for the task to be considered as complete. Note: this is a separate task and is only implemented to satisfy a separate request to check if the reward can be useful in improving performance of a pre-trained policy. The protocol defines paired evaluation and a separate confirmatory split. The pretrained-policy pilot has not been run, so there is no evidence yet that optimizing this reward improves policy performance.

Other tasks, such as extending the types of mathematical contracts that can be solved, automating the process of creating the contracts and using larger datasets for training have been separated from this task and will be handled in separate projects, to ensure that this project is completed in a bounded timeframe.

The main lesson learned from this project is the separation of roles that can be achieved by having an environment, that can encode the contract of the question, a model that can provide data for answering the question and a checker that can provide an interpretable reward to the agent, without providing a reference candidate answer.

This project is publicly available on GitHub under the MIT license here: https://github.com/stanleyngugi/mathcheck-rl

Companion article about the Engine and other artifacts generated by the engine can be found [here](https://github.com/stanleyngugi/mathcheck-engine/blob/main/TECHNICAL_ARTICLE.md).
