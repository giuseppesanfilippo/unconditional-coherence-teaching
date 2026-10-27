# Unconditional Coherence — Teaching Tool

An English Streamlit application for learning de Finetti's coherence criterion
for finite assessments on unconditional events.
Try the application online on [Streamlit](https://unconditional-coherence-teaching.streamlit.app).

The application accepts Boolean event formulas, assessed probabilities, and
logical relations. It constructs the logical constituents and checks whether
the assessment belongs to their convex hull:

\[
Q^T\lambda=p,\qquad \sum_k\lambda_k=1,\qquad \lambda_k\geq 0.
\]

## Run locally

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

The Boolean syntax is `and`, `or`, `not`, and parentheses. Logical relations
are required to be true and are entered one per line. For incompatible events,
you can write either `not (A and B)` or the equivalent, more explicit form
`A and B = False`. Similarly, `A or B = True` requires that at least one of
the two events occurs. Implication can be entered directly as `A implies B`;
this means that `A and not (B) = False`, or, in mathematical notation,

\[
A\Rightarrow B\quad\Longleftrightarrow\quad A\land\overline{B}=\bot.
\]

An empty relation is ignored.

## Educational interpretation

Each constituent is a logically possible truth pattern for the assessed
events. Its point `q_k` is the corresponding zero-one vector. Coherence means
that the probability vector `p` is a convex combination of these points. The
constituents are ordered from the all-true pattern towards the all-false
pattern. Each event row can be moved up or down or removed individually.

After a coherent assessment, the app also displays the explicit linear system:
one equation for each assessed event, the normalization equation, and the
non-negativity constraints for the constituent weights.

The app also computes the coherent extension interval for a further event `F`:

\[
z'=\min\sum_k\lambda'_k q_{k,F},\qquad
z''=\max\sum_k\lambda''_k q_{k,F}.
\]

For both bounds, the interface displays the complete feasible system: the
original assessed-event equations, the normalization equation, and the
non-negativity constraints. The lower bound minimizes the total weight of
constituents in which `F` is true; the upper bound maximizes the same quantity.

The interface displays each constituent in LaTeX. For example, a constituent
with `A` true and `B` false is written as
\(C=A\land\overline{B}\). Repeated or logically redundant factors are
simplified automatically; for instance,
\(A\land B\land(A\land B)=A\land B\). The extension examples include the
conjunction `A and B` and the union `A or B`.
