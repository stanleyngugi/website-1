# Building a Grammar for AI-Generated Mathematical Proof Steps

_What a small grammar captures, what its fallback gives away, and how to measure the difference._

Lean is a language and tool for writing computer-checked mathematical proofs. A _tactic_ is a command that advances a proof; this article studies grammars for those individual proof steps.

> **Updated September 5, 2026.** Expanded from the August 22 article with executable examples, a grammar ablation, and explicit measurement definitions. The original corpus figures are retained as historical observations, with their extraction limitations explained below. [Original version](https://stanleyngugi.netlify.app/archive/revisions/2026-08-22-lean-tactic-language-cfg-original) · [Evidence and reproduction](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/evidence.md).

A grammar for Lean tactics begins with an attractive observation. Many proof steps start with a familiar word: `rw`, `simp`, `exact`, `apply`, `intro`. Behind a large mathematical library there appears to be a comparatively small vocabulary of actions. If a language model repeatedly uses those actions, perhaps a compact grammar can guide its generation without representing the entirety of Lean.

The interesting work begins when we ask what “representing a tactic” means. Consider three lines:

```lean
rw [mul_comm]
simp only [h₁, h₂] at h
exact f x
```

Recognizing their leading words is easy. Checking that the rewrite list closes, that `at` has an appropriate location, and that the term after `exact` is syntactically well formed is a different task. Determining whether `f x` proves the current goal is another task again.

I built a small Lark grammar, extracted tactic-like text from Mathlib, and measured how often the grammar accepted that text. The original report recorded 99.86% acceptance on 144,154 extracted entries. That was an encouraging corpus-fit result. Subsequent inspection showed why it cannot stand alone: the grammar is permissive, the extraction has structural limitations, and an English sentence can receive the same acceptance verdict as a real tactic.

What do we want our grammar to do? This is a somewhat philosophical question. For instance, it might be simply a label for common syntax (and therefore exclude other syntax), it could be an interface description so that the model will output what we want. It could be all of these, and have different evaluations. It might be the same code. We’ll talk about these as we explore the actual grammar and give some examples. Also, we will discuss some of the actual effects of using such a grammar in this companion article: [Grammar Constrained Decoding: Trying it out on Lean](/posts/2026-08-22-grammar-constrained-decoding-lean.html). This is not a complete theorem prover, just a study of one representation and its effects.

## A useful subset is a design decision

A note about ‘a useful subset’: Lean is very extensible. It allows syntax extension and implementation of new tactics. This grammar isn’t meant to run inside Lean, so we need to limit its scope somehow. It could be a limitation to a certain environment, or collection of forms, or just an approximation.

Lean has a very interesting parser architecture. To get a feel for the types of things we need to parse, the syntax types are a good start. In particular, we need to have a feel for the differences between these types and not re-invent the pattern matching dispatch on keywords. In particular, the syntax for tactics is interesting, and how it interacts with the elaborator, so we refer to the reference manual on this: [Custom Tactics](https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Custom-Tactics/)

Initially, for me, the approach to defining this grammar was a bit hacky, and mostly looked for keywords. Mostly, the arguments to keywords weren’t specifically limited. However, often there was a common form, and it was coded as an alternative.

To review, we want to make something that is good for both classifying the surface form (common ones) as well as constraining the decoding. These are not necessarily the same thing.

Finally, a note about the grammar: this grammar was more of an experiment, and it differs in some ways from the initial proposed architecture. In particular, the initial proposal had more specific forms for the rewrite list, arguments to simplifier, locations, control constructs, etc, whereas this one left more to the catch-all.

Before reading the next section on the percentage, let's look at the actual design. This is a shortened version of the actual file; in fact, it contains 53 tactic alternatives for the forms including both focus and case where arms, as well as the generic one. The number 53 is not the number of definitions in the grammar but the number of alternatives for the non-terminal `tactic`.

```lark
start: tactic

tactic: rw_tac
      | exact_tac
      | rfl_tac
      | generic_tac

rw_tac.2: "rw"i ARGS
exact_tac.2: "exact"i ARGS
rfl_tac.2: "rfl"i

generic_tac.-1: IDENT ARGS?
IDENT: /[A-Za-z_][A-Za-z0-9_'!]*/
ARGS: /.+/

%import common.WS
%ignore WS
```

Here the digits `.2` and `.-1` at the end of some definitions influence how Lark interprets the grammar, and similarly the `i` at the end of some literal definitions indicates they should be interpreted case-insensitively.

As an example, notice that the non-terminal `rw_tac` expects to see a literal "rw" followed by some arguments, but those arguments are not expected to be a list. In fact, the non-terminal `ARGS` simply matches an arbitrary string matched by the regular expression. In particular, there is no definition of what it means for a closing bracket to match an opening bracket. Similarly, the non-terminal `exact_tac` does not parse the application tree in, e.g., `f x`. In fact, it just takes whatever is left of the text.

Finally, note how the line "rfl nonsense" would not match the non-terminal `rfl_tac`, but it would match the non-terminal `generic_tac`. The priority of the non-terminals simply determines which one should be used if both can match.

Finally, here are some actual counterexamples that can be run yourself:

|Input string|Historical tactic scoring would class this as|But it is in fact|
|---|---|---|
|`rw [`|A named tactic, namely rewrite|A list of arguments which is not closed|
|`exact (`|A named tactic, namely exact|An incomplete term|
|`rfl nonsense`|A generic tactic form|An invalid use of a fixed tactic (which may take arguments in some forms)|
|`sorry`|A generic tactic form|An omitted keyword|
|`The first step is to induct on the structure of n.`|A generic tactic form|A piece of English prose, which to be fair starts with a valid identifier|

These aren't hypotheticals; these are accepted by the [companion code](https://github.com/stanleyngugi/ai-proof-grammars). And the problem isn't solved by saying "fine, the grammar is just a category gate"; this accepts input that isn't in the category it's supposed to accept!

The most we can say about the grammar above is that it accepts some relatively broad set of identifier-led surface forms with a bit of structure on top. Whether this kind of bias helps our generation is something we'll explore in [article 2](/posts/2026-08-22-grammar-constrained-decoding-lean.html).

## What does explicitly modelling some structure give us?

Consider the following much smaller grammar:

```lark
start: rw_tac
rw_tac: "rw" "[" name ("," name)* "]"
name: /[A-Za-z_][A-Za-z0-9_'.]*/
%import common.WS
%ignore WS
```

This small teaching grammar enables us to accept something like `rw [mul_comm]` or `rw [h1, h2]`. It will reject incomplete input like `rw [`, but it does reject valid Lean syntax, like those that include the ← character or more involved terms. These are choices about how wide to make the scope of the grammar.

If we add an alternative `generic_tac` like we had before, we'll immediately lose some of this guarantee, because now the grammar describes the union of the languages of the alternatives. We'd have to think carefully about what valid and invalid examples might now be accepted again.

To be clear, this isn't about some impossibility of modelling all term syntax with a grammar. There are lots of pieces of syntax that we could model quite well with a grammar, such as lists, delimiters, optional clauses, bounded arguments, etc., that don't require name resolution or type checking. It is instead an engineering decision of how much expressiveness and precision we want in our grammar, and how much we want to have to maintain.

What happens if I remove these and re-run measurements? Just to confirm, the input will still be the same, just the grammar I use will be the one below (i.e. the generic identifier-led rule, and two structure rules):

```lark
start: tactic
?tactic: generic_tac | focus_tac | case_arm_tac

generic_tac: IDENT ARGS?
focus_tac: "·" tactic
case_arm_tac: "|" CASE_PATTERN "=>" tactic?
```

The above grammar, I believe, has lexing rules consistent with the scoring grammar used for the historical numbers. I ran both the above and the scoring grammar on the first cleaned line of all saved Qwen model outputs (to be consistent with the column under Qwen in the original Qwen score table). The results are in the table below.

|Saved outputs |Accepted using full scoring grammar |Accepted using the reduced grammar |Number of disagreements |
|---|---|---|---|
|Unconstrained Qwen |420/640 |420/640 |0 |
|Constrained Qwen |640/640 |640/640 |0 |

While this is not a proof that the grammars accept the same language, I think it is good evidence for it being true (ignoring differences in how quickly they can be compiled/run). The only functional difference between the two grammars, as far as I can tell, is in the names of the alternatives that can be accepted.

This goes some way to explaining the disconnect between the large percentage of named matches and the low percentage of rejections, I think.

I think it will be important to be careful to separate out investigations of different ways of representing the same accepted language, vs investigations of accepting different languages, while keeping other implementation choices fixed.

## Two measurements, with two denominators

For a reference collection of extracted entries, corpus acceptance is:

```text
coverage = accepted reference entries / tested reference entries
```

For a specified corruption experiment, rejection is:

```text
rejection rate = rejected mutated entries / tested mutated entries
```

A grammar that accepts every string gets perfect coverage and rejects nothing. High coverage is therefore not sufficient evidence that a decoder constraint eliminates malformed output. Conversely, an aggressively restricted grammar may reject many malformed strings while also excluding useful tactics.

The denominator is part of the measurement. Reference entries could be physical lines, logical tactic applications, complete proof blocks, or distinct strings. Those are different populations. A proof containing repeated `simp` calls contributes differently to a frequency-weighted corpus measure and a deduplicated measure.

For the corruption experiment, the mixture matters just as much. Truncation, prose replacement, argument shuffling, and random identifier sequences probe different behaviours. Changing their proportions changes the aggregate. Some mutations also remain valid Lean: swapping one real keyword for another is not a ground-truth test of syntactic invalidity. It measures sensitivity to that replacement.

The revised mutation run makes those denominators explicit. It sampled 5,000 entries from a later Mathlib checkout, retaining the historical heuristic extractor. Nine untouched entries were rejected. Each entry received one randomly chosen mutation; unchanged mutations were excluded. A separate pool contributed 1,630 candidate prose lines harvested from saved Goedel outputs. That pool is selected by textual heuristics, not human-labelled ground truth.

| Mutation or candidate class | Rejected / tested | Rejected |
|---|---:|---:|
| Truncation | 1 / 854 | 0.12% |
| English-word lead | 0 / 824 | 0% |
| Different real tactic keyword | 0 / 795 | 0% |
| Argument shuffle | 1 / 725 | 0.14% |
| Full token shuffle | 217 / 741 | 29.28% |
| Identifier soup | 0 / 844 | 0% |
| Harvested prose candidates | 0 / 1,630 | 0% |
| Combined | 219 / 6,413 | 3.41% |

<figure>
<img src="/assets/cfg/mutation-rejection.svg" width="820" height="480" alt="Full token shuffle rejects 217 of 741 examples; truncation and argument shuffle reject one each; the remaining four classes reject zero." loading="lazy">
<figcaption>Rejection depends strongly on the mutation class. Counts and the historical extraction procedure are part of the result.</figcaption>
</figure>

Most rejection comes from shuffling the entire string, which can move punctuation into the leading position. Replacing a keyword with an English word leaves the broad identifier-led shape intact. That pattern is consistent with the grammar rules we inspected, and it is more informative than the aggregate alone.

This dated rerun used Mathlib commit `53c82c1c23ec418ebf7290390bc8108957bef853`: 8,373 files under its Mathlib subtree and 145,168 extracted entries. It is not a reconstruction of the initial corpus. The original addendum’s 3.5% also came from different accounting: its combined numerator omitted prose rejections while its denominator included prose. The revised script and provenance record make both the class mixture and the calculation inspectable.

## Extracting the corpus is part of the experiment

In the original post on this, I talked about a series of improvements to this extraction process, finding that the problem the initial “merge together lines with only brackets on them” was splitting continuations a bit too early, and that using a version that was also aware of indentation reduced the number of entries quite a bit. I then went on to observe that handling the arms of cases statements eliminated a common failure mode, and that by looking at the failures we could understand whether they were due to unsupported forms in the grammar or due to problems in the text extraction.

However, while auditing the code recently, I found a way in which the historical extractor was merging too much: it was merging together lines that started with more indentation before it had determined where the individual proof steps were. For example, it would extract

```lean
example (p q : Prop) (h : p ∧ q) : q ∧ p := by
  constructor
  · exact h.2
  · exact h.1
```

as a single entry:

```text
constructor · exact h.2 · exact h.1
```

While this contains some of the right words, it doesn’t contain the right structure, and isn’t the right thing to be counting. (It does parse, using the generic argument slot in the grammar, so it wouldn’t have been found by auditing parse failures.)

This changes some of my understanding of the coverage of the corpus and the concentration of keywords it contains. It also shows a few of the pitfalls of processing Lean source files as text: block comments are nested and so can’t be removed with a non-greedy regular expression, characters inside strings shouldn’t count towards brackets, and layout information is used to separate nested proofs from wrapped arguments. For reproducibility, I will keep using the historical text extraction for now, but I note these caveats.

In future, we will want to understand the syntax of Lean programs better, perhaps by getting the spans from the Lean compiler itself or by looking at elaboration traces. We will also want to understand the provenance of our corpus, so that we know which file each entry came from, where in the file it was, and what environment it was in. For the purposes of this article, however, it is sufficient to know exactly what corpus we are working with, and not claim that it is necessarily all of the verified tactic applications in Mathlib.

### The table of the fractions of the historical corpus in the original report

|type of classification|number of entries|percentage|
|---|---|---|
|named alternative exists|133224|92.4 %|
|only generic fallback|10725|7.4 %|
|no classification (rejected)|205|0.14 %|
|In total|144154|100.0 %|

Unfortunately, the original corpus for which this was done in its original immutable revision, as well as the full artifact extracted from it, is not included in the companion repo provided here. So this revision of the corpus does not actually run on the original corpus, but as explained in the [provenance document](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/provenance.md), it does run on a later local checkout of Mathlib that is available.

Moreover, this does in fact give evidence that the leading keywords are used in a very concentrated manner. Even if one takes the full pass into account, the top 20 leading keywords cover 84.9% (now 82.4%) of all uses. So maybe this is actually a good starting point for investigating more compact vocabularies of actions. However, this does not give any information about the distribution of tactic applications that would be independent of the way the data was extracted.

For this, one would have to compare with another extraction procedure such as the one underlying Lean4trace (see [Lean4trace](https://openreview.net/forum?id=sjLWmLeJ6R)), which actually uses the Lean elaboration machinery to extract its training data. However, it should be noted that even if both procedures gave exactly the same percentages, that would not constitute a validation of the set of theorems that were extracted, since that would only show that the same procedure gives the same results on a different checkout, but would not remove systematic errors.

This is just to document the motivation for the experiment. If one wants to make a stronger claim, one should validate the corpus used for counting.

## Macros as a controlled interface

In the original project there was a second idea for trying to tackle this, which was to use Lean macros to produce some regular interfaces for running various tactics, and then wrapping those:

```lean
macro "solve_positivity" : tactic => `(tactic| positivity)

macro "discharge_linear" e1:term:max e2:term:max : tactic =>
  `(tactic| linarith [$e1, $e2])
```

For the second one (which is the only one that takes multiple arguments), the precedence stuff is a bit of an issue, so if those arguments are complex then they will have to be wrapped in brackets. But anyway, the whole suite of macros and all the things it imports is still there in the original consolidated experiment.

This doesn't help at all if the grammar is accepting those as arguments already, but it might be a way of binding some operations to something that can be expressed in the external grammar. It's only worth doing for some operations though, because something like the rename of positivity is pretty useless.

That's an option in the language design, although as noted before that doesn't mean that it's going to work for any given macro.

## Designing an output language instead of only describing one

But that leads on nicely to a more general point, which is a question about the original proposal. Is it necessary that the language is exactly the same as the one that the human authors are writing in? There's quite a bit of difference between designing a grammar for a given corpus, and designing a nice interface to a selection of operations. They're quite different research objectives.

To be more concrete, a few examples of features that this interface might have, that the standard one doesn’t:

In general, we want something that’s easy for us to maintain and extend while still being expressive. Adding a new operation should involve adding a production to the grammar and implementing that operation. We can also do things like write tests for this interface to make sure that we’re accepting all the examples we want to, and rejecting nonsensical combinations of arguments early. And we can move complexity that’s specific to some library into that library, while maintaining the same expressive power.

There are also some downsides. For one, it might be harder for a model that’s already trained on Lean to use. It might also be the case that it’s harder for a model to figure out good strategies in this interface; making the interface “too coarse” might make it harder to search, just as making it too fine-grained makes it take too many steps to generate anything. And finally, even with the macros, it’ll be hard to show that the interface is “semantically complete” in a sense, since it’s not realistic to show that any tactic we might want to use can be supported by the interface with a finite set of operations.

It’s also hard to show empirically that the interface is “complete enough” with our current method of fitting a corpus, since that’s inherently tied to the particular interface we’re fitting. To do this properly, we’d want to compare different interfaces on a fixed set of tasks, with a fixed set of available operations, and see which one performs better on those tasks (along with other metrics like how often it generates malformed arguments, what fraction of the arguments it accepts, how long its outputs are, etc.). But that’s kind of a weak test, since it requires the interfaces to be fairly similar (it wouldn’t be very interesting if the only difference was that one interface used “introduction” as a keyword and the other used “intro”).

Finally, a quick note on terminology: while this post talks primarily about designing a grammar for actions that an agent can take in an environment, I had a few other use cases in mind when I first started this project. In particular, I think this could also be useful for either (a) designing a grammar that is used to more accurately describe/understand some environment, or (b) designing a grammar that we can use to sample from (i.e., we want to restrict the things we sample to be “valid” in some sense). My current results are more directly relevant to these two goals, but I hope to have results relevant to the first goal soon.

## Rocq and Isabelle

That work, in addition to building the grammar, did a bit more, for which the log may be instructive. It also experimented with a Rocq (SSReflect) grammar, and an Isabelle grammar. In brief, it could accept 98.81% of the Rocq units it was given, and could accept 95.47% of the text corresponding to proof steps of a selected Isabelle file. These were explored with different extraction procedures, so don’t take these as a definitive measure of the comparative complexity of these languages.

Note that Rocq has proof delimiters, but the splitter didn’t take account of that, it merely split at all top-level “.”, and furthermore it did not take account of qualified names. Also, the Isabelle work was done without executing in the Isabelle kernel, and again the extraction of statements from the text required some attention to Isabelle syntax, for example taking account of proof headers, quoted terms, and wrapped fact references such as `using X[of ...]`.

For completeness, here is the [file of Rocq macros](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/post1-tactic-cfg/rocq_macro_bridge.v), which includes five small examples of “Tactic Notation”. Note that terms passed as arguments are parenthesised, so perhaps there are no issues with precedence etc in Rocq.

Ultimately, the lesson of this post is methodological: always be clear about what interface is being used; always keep track of the provenance of the source used for analysis; always test on real examples, as well as counter examples; always know what the units of the percentages are and what language they are accepted in!

## Reproducing the checks

There is also a [companion repo](https://github.com/stanleyngugi/ai-proof-grammars) with all inputs and analyses, to reproduce the checks done in this article. To do so, it’s not needed to have a GPU or run Pantograph, simply:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-analysis.txt
python analysis/audit.py
python -m unittest discover -s tests
```

All the exact numbers and acceptances, including which samples didn’t agree with the reduced grammars, and the SHA-256 hashes of the inputs used, can be found in `analysis/audit.json`. All the counterexamples shown here are checked there. To run the mutation pass yourself, given a path to a Mathlib copy, without overwriting the historical data, run:

```bash
python post1-tactic-cfg/strength_analysis.py \
  --mathlib /path/to/mathlib4 \
  --out analysis/strength.json
```

Note that this will use the historical version of the heuristic extractor, and the results will be marked as such. The fixes to arithmetic and paths do not turn it into a real Lean parser. For more information on which figures can be regenerated, and which are simply stored from the historical run of the reporting script, see the [provenance document](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/provenance.md).

Now that we have a compact grammar, it is time to see what effect having the exact accepted language has on our sampling distribution. See the [companion article](/posts/2026-08-22-grammar-constrained-decoding-lean.html).

## References

<div class="refs">
<p>Lean contributors. <a href="https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Custom-Tactics/">Custom Tactics</a>. The Lean Language Reference. Syntax extensions, macros, and elaboration.</p>
<p>Nesterov, V., Kapushev, Y., and Burtsev, M. (2024). <a href="https://openreview.net/forum?id=sjLWmLeJ6R">Lean4trace: Data Augmentation for Neural Theorem Proving in Lean</a>. ICML Workshop on AI for Mathematics.</p>
<p>Lean community. <a href="https://github.com/leanprover-community/mathlib4">Mathlib</a>. The Lean 4 mathematical library. The dated mutation rerun uses revision 53c82c1c23ec418ebf7290390bc8108957bef853.</p>
</div>
