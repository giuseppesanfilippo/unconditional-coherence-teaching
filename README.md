# Unconditional Coherence — Teaching Tool

An English Streamlit application for learning de Finetti's coherence criterion
for finite assessments on unconditional events.

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

The Boolean syntax is `and`, `or`, `not`, and parentheses. An empty relation
is ignored.

## Educational interpretation

Each constituent is a logically possible truth pattern for the assessed
events. Its point `q_k` is the corresponding zero-one vector. Coherence means
that the probability vector `p` is a convex combination of these points.

The app also computes the coherent extension interval for a further event `F`:

\[
z'=\min\sum_k\lambda'_k q_{k,F},\qquad
z''=\max\sum_k\lambda''_k q_{k,F}.
\]
