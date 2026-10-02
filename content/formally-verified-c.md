# An RL Environment Where C Code Has to Be Proved, Not Just Tested

A common approach to generating reward for coding is to use a test suite, where the environment runs the model's code on a selection of inputs.

**Formally Verified C** instead uses formal verification. Specifically, the environment presents the agent with a C function alongside an ACSL specification, and the agent's task is to produce a C implementation that matches the specification. This implementation is then passed to Frama-C, which generates a set of mathematical proof obligations that describe the function's expected behavior, as well as various runtime safety conditions. Finally, the environment translates Frama-C's proof report into reward and feedback.

This repository contains the environment itself, as well as the first public task pack containing 64 C/ACSL problems, reference implementations (verified to be correct), negative controls, and a fixed train/val/test split. Tasks are run using Prime Intellect's [Verifiers v1 API](https://github.com/PrimeIntellect-ai/verifiers/tree/b2e4e8157783b2c0dffc7821044c87f29f1c3ccf/verifiers/v1).

Just as important as the corpus itself is the architecture used to solve the problems. While this repository includes a starting corpus, it is designed to be used with any corpus of C problems and contracts, and any coding agent architecture (e.g. single completion, iterative, more sophisticated harness, etc).

That separation is the foundation of **Formally Verified Code RL**, the umbrella repository and **Formally Verified C** is its first implemented environment.

## From a C function to a proof obligation

Suppose that a simple task is given to be solved, for instance:

```c
/*@ requires x >= -1000 && x <= 1000;
    ensures \result == x + 1;
    assigns \nothing;
*/
int increment(int x) {
  /* TODO: complete this body */
}
```

The commented part before the function is a contract, written in a language called ACSL. As it is syntactically a standard C comment, it is ignored by standard C development tools. However, specific tools will be able to use this information to verify the function against its contract. More information on ACSL can be found [here](https://frama-c.com/acsl.html).

The contract here has three parts: the `requires` clause, which is a set of assumptions on the arguments of the function that will be guaranteed to hold when the function is called; the `ensures` clause, which describes the property that the implementation has to satisfy; and the `assigns` clause, which describes the part of the memory that the function is allowed to modify (here, `
othing` means that the function is not allowed to modify any part of the memory).

In this simple case, it is easy to come up with an implementation, for instance by writing `return x + 1;`. In a standard development process, a set of test cases would be generated to check that this implementation is indeed correct. However, one can also use a program verification tool to check, mathematically, that the implementation is correct for any possible valid input.

Note that even in this simple case, the verification is not trivial, as integers in C are not mathematical integers and it is for instance possible to have integer overflows. More generally, a program can exhibit many kinds of runtime errors, such as invalid memory accesses or modifications of memory locations that should not be modified.

In Frama-C, the WP (for weakest preconditions) plugin is able to transform the program implementation and its contract into a set of logical conditions, generally called verification conditions (VCs), the proof of which entails the properties that were requested to be proved. In practice, WP simplifies these VCs and calls automated theorem provers in order to prove them. The version of Frama-C that will be used for the pinned judge is Frama-C 33.0, with Why3 1.8.2, Alt-Ergo 2.6.3, and Z3 4.8.12. More information on WP can be found [here](https://frama-c.com/fc-plugins/wp.html).

It works by essentially reasoning backwards from the desired result and “pushing” it backwards through the program. In our simple example, it would substitute `x + 1` for the “return” value and see that the post-condition becomes `x + 1 == x + 1`, which is trivially true. (If we’d instead used the incorrect implementation `return x;`, we’d end up with `x == x + 1` which we can see is false for all permitted inputs to the function). For more complicated functions, the process is more involved and results in a variety of different kinds of verification obligations; the verifier is responsible for constructing those objects and reporting them to us.

The verifier can also be instructed to look for possible runtime errors; for example, to ensure that arithmetic operations and pointer accesses don’t result in out-of-bounds values. This is handled by a piece of Frama-C called RTE and can be turned on to cause the WP plugin to generate and prove the corresponding assertions. See the [Frama-C RTE documentation](https://frama-c.com/fc-plugins/rte.html) for more details.

Of course, all of this is still relative to the specification we’ve provided. It’s still up to us to make sure that the specification is what we want, and that it specifies that the function increments its argument, for example. Writing good specifications is challenging, but is assisted by a variety of techniques, including testing, code review, and—yes—formal proof.

## Where Did I Get All These Problems?

I used two different corpora of problems.

First, for early research, I took an external corpus called CASP which consisted of a set of C programs annotated with ACSL specifications. The CASP dataset was extracted and processed from a couple of corpora called “The Stack 1” and “The Stack 2”, and contains 506 instances of specifications that have already been formally verified against their implementation. See the [CASP paper](https://arxiv.org/abs/2508.18798) for more details.

To use this corpus, I re-ingested it using my ingestion pipeline, which replayed the original corpus against my own pinned copy of the verifier, checked that the contracts were something I would admit, and then converted them into completion tasks by removing the target function body and retaining the contract, signature, declarations, and surrounding code.

Second, I prepared a separate, project-authored data pack for the public Core-v1 benchmark. The pack was generated by a coding agent. It consists of 16 tasks expanded into 64 via a carefully coded deterministic task generator. This corpus is separate from the CASP examples that were directly imported. The code for this data pack is the [task generator script here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/scripts/build_core_v1.py), and the development of the data pack is recorded in the [worklog here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/WORKLOG.md).

Tasks in this pack have a contract, a reference body (the correct implementation), and a known incorrect body (negative control). The task generator will generate the completed version with the reference body, a TODO version with just a function header, and a negative control version with the incorrect body. This metadata (task id, source hash, provenance, license, family, etc.) is recorded in the expanded task. Tasks are validated by replay in Frama-C to ensure that the reference and negative body behave as expected. Tasks have been machine-reviewed and machine-verified, but will soon be reviewed by human domain experts.

The tasks have been split into train/val/test sets containing 33, 15, and 16 tasks. Related tasks will appear in the same split to prevent accidental leakage from trivial transformations (renaming variables, modifying constants, etc.). The data pack in this repo contains all of the tasks in the public Core-v1 pack and exercises a variety of concepts (scalar arithmetic, branching, pointer updates, framing, arrays, etc.). A detailed description of the tasks and the data schema is recorded in the [dataset card here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/data/packs/core-v1/README.md).

The CASP dataset used locally to develop this benchmark does not contain sufficient provenance information to ensure that redistribution is permitted for all examples. As a result, the CASP corpus will be treated as a separate research corpus and not released with this public data pack. The tasks in Core-v1 are the starting point for any public task set used for research and released under the Apache-2.0 license.

## Taskset, Harness, and Runtime: Separation of Concerns in Verifiers v1

A key feature of this environment is composability. To that end, this framework uses Verifiers v1’s separation into three composable components:

| Component | Includes | Possible Variations |
| --- | --- | --- |
| Taskset and Task | Problem definitions, contract definitions, task prompts, setup procedures, verification logic, reward definitions, metrics definitions, etc. | Different task packs, different ways of presenting tasks, etc. |
| Agent Harness | Definition of available tools, interaction loop, etc. | Completion harness, bash-based code editing harness, some other coding agent harness, etc. |
| Runtime | Code execution environment, filesystem setup, dependency installation, resource constraints, etc. | Different container and resource configuration |

The formal verification scoring logic is entirely contained within the task implementation. The agent harness does not need to know anything about how to run a formal verifier on C code, for example. The task and taskset implementations follow the same interfaces as Verifiers v1 task and tasksets, and the framework exports the same functions for loading tasksets and environments. You can see the [environment implementation here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/src/acsl_c/taskset.py).

Importantly, this structure allows the same task to be presented to an agent in different ways. For example, in single-turn mode, the task provides a prompt that includes a code skeleton, and expects the model to return a completed C code file. In agentic settings, the task instead writes the code skeleton to a `solution.c` file in the task setup phase, and also writes a `verify.sh` script that can be used to get feedback. The agent is expected to produce changes to the `solution.c` file, which will be scored at the end.

In either case, the formal verification scoring logic remains the same, and is tied to the task. Changing the search procedure does not change the contract the code needs to satisfy.

## Bring your own problems and contracts

By default, the framework loads the `core-v1` task pack, but you can load your own task packs by specifying the path to a directory containing your data, the name of the JSONL files, and the name of a manifest that specifies which tasks belong to which splits. Your data should be formatted as a jsonl file, with one task per line. Your manifest should specify which tasks belong to which splits. Your task pack should include the necessary information for the task implementation to create Task objects, including the C code skeleton, the contract, reference information, task identifiers, and admission metadata.

In a nutshell, to select a pack of tasks that has already been prepared, all that is needed is to, e.g., do

```python
from acsl_c.taskset import AcslCTasksetConfig, load_taskset

config = AcslCTasksetConfig(
    data_dir="/path/to/my-c-acsl-pack",
    data_glob="tasks.jsonl",
    split_manifest="manifest.json",
    split="train",
)
taskset = load_taskset(config)
```

The actual content of the pack is the only thing that needs to change, the code that extracts the source, runs the verifier, cache mechanism, reward components, and other metrics can all be reused. So if someone has some C functions with ACSL contracts that have been accepted, then it would be possible to construct a more domain specific taskset for evaluation purposes using essentially the same judge.

For example, the domain could be a set of numerics that should be bounded and need to transform inputs in a certain way, perhaps for a controller. Some of the functions may need to clamp to a certain interval, others may need to respect certain memory, etc.

It may also be useful to change the prompt style, although the current implementation only supports a “completion” mode where the prompt is constructed from the `skeleton_c` field of the task data, which includes both the C context and the formal specification. Although it would be possible to change the prompt generation and setup methods of the task while reusing the scoring methods, and thereby the existing task loader, it is important to note that the task would still need to be provided in a formalized manner following the structure explained above, it will not be possible to simply provide a set of requirements in free form and expect the task to be able to interpret it.

A note on how the task pack was prepared can be found [here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/data/packs/core-v1/README.md).

It is worth pointing out that the project may still be useful even though the dataset is small.

## From one completion to an iterative coding agent

While a simple, short scalar function may require only one completion to implement correctly, a more complex implementation may be better served by a multi-turn agentic approach, where the model can iteratively modify its implementation in response to feedback about unmet obligations in its contract.

To facilitate this, the included training and evaluation configuration files contain both single-turn and agentic examples. The agentic example utilizes the bash harness with edit capabilities enabled, with a total budget of 8 turns and 16384 tokens:

```toml
[[eval.source]]
name = "formally-verified-c-agentic-validation"
env.taskset.id = "formally-verified-c"
env.taskset.task.agentic = true
env.agent.harness.id = "bash"
env.agent.harness.edit = true
env.agent.max_turns = 8
env.agent.max_total_tokens = 16384
```

The above is an abridged version of the configuration file that would be placed under the evaluation source configuration; see the [full configuration file here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/configs/agentic_eval_v0_9.toml).

Additionally, Verifiers v1 includes agentic adapters for a variety of coding harnesses, including Codex, which is included in the pinned revision of Verifiers that this environment uses. The current configuration repository only includes single-turn and bash harness configurations; to use the Codex harness, modify the configuration file and provide the necessary runtime dependencies. See the [pinned Codex harness implementation](https://github.com/PrimeIntellect-ai/verifiers/blob/b2e4e8157783b2c0dffc7821044c87f29f1c3ccf/verifiers/v1/harnesses/codex/harness.py) for details.

This setup allows for interesting comparisons between agentic harnesses and their efficacy at solving programming tasks, given the same set of contracts, the same model, and the same overall token budget. For instance, one may find that an iterative agentic approach is more effective than a single-turn approach at fully proving a given set of contracts.

## Turning proof reports into reward

In the environment, unlike an all-or-nothing proof indicator, not all unsuccessful proof candidates are created equal. A proof candidate that doesn’t even parse is not the same as a proof candidate that has discharged all proof obligations except for showing that some arithmetic doesn’t overflow. The environment reflects this by using a staged reward scheme. Specifically, the reward is

```text
0.10 * parse_compile_and_nonempty_goal_gate
+ 0.50 * proved_verification_condition_fraction
+ 0.20 * all_goals_fully_proved
+ 0.20 * proof_gated_fixed_contract_integrity
```

The first term is non-zero iff the candidate parses and compiles, the proof report has at least one goal, and the process exits cleanly, the second term reflects the fraction of proof obligations proved (as indicated in the report), and the last two terms are non-zero only if there is a full proof. Further, the last two terms are only non-zero if the fixed contract and code outside the target function body are unchanged. If either is changed, all terms are zero; the target function body is the part the agent is meant to edit.

So, for example, a proof that results in a clean, compiled proof report indicating 8 proof obligations proved (out of a total of 10 proof obligations), with the fixed context intact, will get a score of 0.5. A score of 1.0 is attained only if the proof is successful (no proof failures or timeouts).

Proofs that time out are not considered fully proved (and will not be cached) because that means that whatever policy was used for selecting solvers was ineffective. They may, however, get a non-zero score if the process exits cleanly and the partial proof information is consistent.

Proof diagnostics, such as failed proof goals, number of proof timeouts, proof tool crashes, source digests, and a de-duplicated history of scoring verdicts are recorded. Note that the history currently only contains structured information about what the scoring hooks have verified; recording information about intermediate agent edits is left as an instrumentation exercise. See the [reward/parser code](https://github.com/stanleyngugi/formally-verified-code-rl/tree/main/environments/acsl-c/src/acsl_c) for details.

## Making verification repeatable

Is the proof result only dependent on the source file?

Many factors are relevant, including the versions of the used provers, the enabled checks, the time-out and resource values. During development, a reference file for the research paper with 112 proof goals would pass the original verification, then time-out during replay with 4 workers, and finally pass during single worker replay. Another file would fail to discharge one obligation with a 20s limit per SMT solver call, then pass with a 60s time-out. To limit these issues, a file is only admitted into the release when it passes during serial replay with the declared time-out for the SMT solver calls. One needs both the code and the policy for running the code to reproduce a proof result.

The judge runs inside a container with bounded resources and an empty default allow-list for network access. The content digest of the published image is available [here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/RELEASE_NOTES_V0.1.7.md#release-artifacts). For the reward, the runner disables the implicit WP cache of Frama-C and instead uses a cache of verdicts that is local to the project. The key of this cache is the source file, the label of the tool-chain, the prover selection, the time-out and a digest of the runner script. Changing any input to the verifier will change the identity of the cache.

The report parser of the judge should not interpret a string containing "false" as boolean true, nor should it interpret a missing report, an impossible count, a compilation failure or a non-zero exit code of a process as success. Environment version 0.1.7 includes these checks, and a reconciliation of the proof result reported and the state of the execution when computing the score in production. Please see the [release notes here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/RELEASE_NOTES_V0.1.7.md).

Out of the 399 files re-verified from the CASP material for the research, 61 of these would still be proven when their implementation was replaced with trivial stubs. These have not been admitted into the release. This is a conservative measure to exclude weak tasks. Note that a contract that is not logically vacuous can still be fulfilled by a trivial implementation. The screening procedure merely flags tasks for either exclusion or review.

**Follow-up audit of September 26, 2026:** Admitted assumptions in the body that is subject to edit and a writable verifier executable in the agent runtime could both be exploited to obtain full reward even for incorrect code.

Adding trivial assertions could also inflate the partial VC reward. Thus, the next phase of hardening should separate body-level proof assumptions from the final judging, and the final judging logic should not be part of the state the agent can write to. Furthermore, required proof obligations and proof assumptions added by the agent should be separated. Finally, when replaying solutions offline, the same logic for reconciling the exit status should be employed. These are follow-up hardening concerns for this alpha. The release evidence below predates this audit and does not establish that these cases are blocked. Passing the existing test suite does not, by itself, resolve them.

## Release Evidence

Evidence for the Core-v1 release was generated Sept. 11th, 2026 for verifying the Core-v1 release and then again Sept. 13th 2026 for verifying the v0.1.7 package.

|Check|Result|
|---|---|
|Public tasks (train/validation/test)|64 (33/15/16)|
|Full Proof on Reference Impls.|64/64|
|Proof Obligations Discharged|296/296|
|Included in Above, RTE Oblig. Disch.|84/84|
|Wrong Impls. Denied Full Proof (Det. Qed Gate)|64/64|
|Ref./Det. (-) Solver Timeouts|0|
|Automated Tests Passed|57|

This release’s evidence can be found [here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/environments/acsl-c/artifacts/core-v1-public-release-evidence.json). Note that the negative gate here, rather than relying on a lack of proof to establish a counter example, simply relies on the Qed simplifier built into WP to check that the wrong control implementations are not accepted. The evidence includes the dataset, data manifest, replay artifacts, and package wheel hashes.

When developing this environment, 316 tasks from the CASP competition were used as a research corpus to aid in development. These tasks, when replayed serially, result in the discharge of 5205 obligations, including 1264 runtime error obligations.

Finally, in testing the package distribution, two simple bugs were found, one related to an ignore file at the environment level, and the other related to including the license in the package. Another bug found was that the tests would rely on the research data in the working repository, so the tests would pass if run in the working repository, but not when installed from a clean download from the Hub. This has since been corrected, and all 64 tasks are loaded, and 57 tests pass, when the corrected source is loaded without the research corpus. A final audit of the tests was performed Sept. 26th, which confirmed that the tests pass.

Feasibility exploration: early end-to-end engineering run with Qwen2.5-Coder-1.5B on an RTX A4000. GRPO (group relative policy optimization) for 12 steps, ~190 episodes, all the way from model generations through Frama-C and reward computations to optimizer updates, without scoring errors. Historical records can be found [here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/RUN_RESULTS.md).

At the end of the run, the batch reward improved from 0.375 to 0.875, albeit without controlled experiments due to (1) task order being correlated with task difficulty and (2) not keeping the baseline run with the paired checkpoint. Nevertheless, this was a sanity check that the whole run can work. Further studies are needed to check if there is actual improvement in proof rate on held-out test tasks.

Memory exploration: leveraging quantization and LoRA (low-rank adapters) to run bigger models like Qwen2.5-Coder-7B on Colab Tesla T4 GPU. The 7B model in 4-bit loading takes 5.39GiB of memory. LoRA pushes the memory usage to a peak of 7.61GiB during the optimizer step for a context length of 2048. This opened up the possibility of doing further studies on Colab, for which there is a [runbook here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/COLAB_RUNBOOK.md). LoRA adapter saving and reloading has been done, and a trial for serial rollout and update with a small budget has been completed, with [results here](https://github.com/stanleyngugi/formally-verified-code-rl/blob/main/docs/COLAB_SERIAL_CANARY.md). Also probed the 14B model with a peak of 12.16GiB for a shorter context length.

The Colab trials were with managed infra and explicit stub labels for rewards (as the Docker judge was not hosted there yet). Further studies for actual learning are in the pipeline.

## Previous work on using formal feedback in code generation

VeCoGen shows how to generate and iteratively improve C programs with formal feedback. Re:Form explores reinforcement learning guided by a verifier, in Dafny. Both of these, and other projects, motivated a more modular and reusable approach to taking advantage of formal feedback in model development, which this project is part of.

[VeCoGen](https://arxiv.org/abs/2411.19275) · [Re:Form](https://arxiv.org/abs/2507.16331)

This project, “Formally Verified C,” provides an installable C/ACSL environment with replaceable task data, task-owned scoring logic, harness selection, a pinned judge, and recorded evidence for each release.

This project implements tasks and rewards using Verifiers v1. OpenEnv is related infrastructure for deploying and consuming agent environments. OpenEnv was originally launched in collaboration between Meta-PyTorch and Hugging Face, and is now coordinated by a larger committee of all involved parties. OpenEnv’s current focus area is standardizing deployment and consumption of agent environments, deferring reward specification to specialized libraries.

[OpenEnv launch](https://huggingface.co/blog/openenv) · [OpenEnv scope and governance](https://huggingface.co/blog/openenv-agentic-rl)

## Some suggested experiments for people using this project

Fix the contracts and scoring, and compare a straightforward completion to solving the tasks iteratively in bash or with Codex. Fix the harness and compare a straightforward binary proof reward to various partial credit schemes. Replace the task pack (Core-v1) with a pack targeting a different domain, and observe transfer.

Some suggested extensions to the task design would aim at tasks that cover reasoning over loops, multiple functions, and larger workspaces, subject to the rules on source code handling and integrity. The tasks here include a small pack intended for public use.

An interesting future direction is to flip the paradigm to have the agent provide the specification (in the form of ACSL contracts), and then to subject those specifications to a review process that evaluates their quality (do they meet the requirements, are they consistent, do they handle negative examples as expected, etc.). In a high-assurance setting where this work is being done because of regulatory requirements, the review process is likely to exist anyway, so it would make sense to have the specification tied to the requirement, review the specification, “freeze” the specification, and then have the agent look for an implementation that meets the specification. There’s a lot of interesting research to be done here!

If this interests you, and you want to try it out today, it’s also possible to bring in specifications that are already trusted.

## What “formally verified” covers here

The proof is relative to the ACSL contract and the pinned C and verifier models. It doesn’t automatically cover behavior outside those models, and it doesn’t prove that the specification captures everything a person intended.

The trusted computing base includes Frama-C’s models and verification-condition generator, Why3, the selected automated provers, the container and runtime boundary, and the environment’s result parser. Those components are trusted here; this release doesn’t formally verify the verifier stack itself.

Core-v1 is machine-reviewed and machine-verified, with independent expert review still to come. The 64 tasks are a small starting pack, and the GPU runs described above don’t establish a learning improvement on held-out tasks.

## Try the environment

The source code, configurations, and evidence are available on [GitHub here](https://github.com/stanleyngugi/formally-verified-code-rl). The environment package is available on the [Prime Environments Hub here](https://app.primeintellect.ai/dashboard/environments/stanley-ngugi/formally-verified-c), and a public task pack is available on [Hugging Face here](https://huggingface.co/datasets/stan4u/formally-verified-c-core-v1).

To try it out yourself, use Verifiers’ v1 API and install the environment (v0.1.7 of the environment, using dataset version Core-v1 0.1.4) using Python 3.11 through 3.13 and the Prime CLI:

```bash
prime env install stanley-ngugi/formally-verified-c@0.1.7
```

To build from source and run the tests:

```bash
git clone https://github.com/stanleyngugi/formally-verified-code-rl.git
cd formally-verified-code-rl/environments/acsl-c
uv sync --extra test
uv run pytest -q
```

To pull the release of the judge used in this blog post (using an immutable reference):

```bash
docker pull ghcr.io/stanleyngugi/formally-verified-c-judge@sha256:b7d7111eac04eb09405842b64af5084f671c8815f90a3d9ea7f5de92f0bcd593
```

Give it a try, either with the bundled tasks or by providing a compatible task pack of interest! Also feel free to provide different harnesses to try out the scoring machinery to evaluate how an agent does solving the problems!
