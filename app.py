"""English teaching interface for unconditional coherence."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logic import Event, check_coherence, coherent_extension_interval  # noqa: E402


st.set_page_config(page_title="Unconditional Coherence", page_icon="∴", layout="wide")


EXAMPLES = {
    "Custom assessment": {
        "description": "Enter your own events and logical relations.",
        "events": [("A", 0.6), ("B", 0.4)],
        "relations": "",
    },
    "Two mutually exclusive events — coherent": {
        "description": "A and B cannot occur together; P(A)=0.4 and P(B)=0.3.",
        "events": [("A", 0.4), ("B", 0.3)],
        "relations": "not (A and B)",
    },
    "Two mutually exclusive events — incoherent": {
        "description": "The probabilities add to more than one, so coherence fails.",
        "events": [("A", 0.7), ("B", 0.6)],
        "relations": "not (A and B)",
    },
    "Complementary events": {
        "description": "B is the complement of A and P(A)=0.7, P(B)=0.3.",
        "events": [("A", 0.7), ("B", 0.3)],
        "relations": "A or B\nnot (A and B)",
    },
}


def _initialise() -> None:
    st.session_state.setdefault("example", "Custom assessment")
    st.session_state.setdefault("events", EXAMPLES["Custom assessment"]["events"])
    st.session_state.setdefault("relations", "")


def _load_example() -> None:
    example = EXAMPLES[st.session_state.example]
    st.session_state.events = list(example["events"])
    st.session_state.relations = example["relations"]
    for index in range(10):
        st.session_state.pop(f"formula_{index}", None)
        st.session_state.pop(f"probability_{index}", None)


def _add_event() -> None:
    index = len(st.session_state.events) + 1
    st.session_state.events.append((f"E{index}", 0.5))


def _remove_event() -> None:
    if len(st.session_state.events) > 1:
        st.session_state.events.pop()


def _render_result(result) -> None:
    if result.coherent:
        st.success(result.message)
    else:
        st.error(result.message)

    rows = []
    for number, constituent in enumerate(result.constituents, start=1):
        rows.append(
            {
                "constituent": f"C{number}",
                "truth pattern": " / ".join(
                    "true" if status else "false" for status in constituent.statuses
                ),
                "q": tuple(float(value) for value in constituent.q),
                "number of witnesses": len(constituent.witnesses),
                "one witness": str(constituent.witnesses[0]),
            }
        )
    st.subheader("Logical constituents")
    st.caption(
        "Several atoms may have the same truth pattern. They are represented by one constituent."
    )
    st.dataframe(rows, hide_index=True, use_container_width=True)

    if result.coherent and result.lambda_solution is not None:
        st.subheader("Convex-hull representation")
        st.latex(r"Q^T\lambda=p,\qquad \lambda_k\geq 0,\qquad \sum_k\lambda_k=1")
        lambda_rows = []
        for number, (constituent, value) in enumerate(
            zip(result.constituents, result.lambda_solution), start=1
        ):
            lambda_rows.append(
                {
                    "constituent": f"C{number}",
                    "q": tuple(float(item) for item in constituent.q),
                    "lambda": float(value),
                }
            )
        st.dataframe(lambda_rows, hide_index=True, use_container_width=True)
        st.write(
            "The assessed probability vector is obtained as a convex combination "
            "of the constituent points using these λ coefficients."
        )


def _render_extension(result) -> None:
    st.success(f"Coherent extension interval: [{result.lower:.6f}, {result.upper:.6f}]")
    if abs(result.lower - result.upper) <= 1e-9:
        st.info("The extension is unique.")
    st.latex(
        r"z'=\min\sum_k\lambda'_k q_{k,F},\qquad "
        r"z''=\max\sum_k\lambda''_k q_{k,F}"
    )
    st.caption(
        "The last coordinate of each q-vector records whether the new event F "
        "is true in that constituent."
    )
    rows = []
    for number, (constituent, lower_value, upper_value) in enumerate(
        zip(
            result.constituents,
            result.lower_lambda,
            result.upper_lambda,
        ),
        start=1,
    ):
        rows.append(
            {
                "constituent": f"C{number}",
                "truth pattern": " / ".join(
                    "true" if status else "false"
                    for status in constituent.statuses
                ),
                "q (including F)": tuple(float(value) for value in constituent.q),
                "lambda' (z')": float(lower_value),
                "lambda'' (z'')": float(upper_value),
                "witnesses": len(constituent.witnesses),
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


_initialise()
st.title("Coherence of unconditional assessments")
st.write(
    "This teaching tool illustrates de Finetti's criterion for probabilities "
    "assigned to ordinary, non-conditioned events."
)

with st.expander("What is the idea?", expanded=True):
    st.markdown(
        r"""
        An **atom** is a complete truth assignment to the primitive propositions.
        The logical relations remove impossible atoms. Atoms that produce the same
        truth pattern for the assessed events form one **logical constituent**.

        If the events are \(E_1,\ldots,E_n\), each constituent has a point
        \(q_k\in\{0,1\}^n\). The assessment \(p=(p_1,\ldots,p_n)\) is coherent
        exactly when it is in the convex hull of these points.
        """
    )

st.subheader("1. Choose or enter an assessment")
st.selectbox("Example", tuple(EXAMPLES), key="example")
st.caption(EXAMPLES[st.session_state.example]["description"])
st.button("Load selected example", on_click=_load_example)

st.subheader("2. Events and probabilities")
updated_events = []
for index, (formula, probability) in enumerate(st.session_state.events):
    left, right = st.columns([3, 1])
    formula = left.text_input(
        f"Event E{index + 1}", value=formula, key=f"formula_{index}"
    )
    probability = right.number_input(
        f"P(E{index + 1})",
        min_value=0.0,
        max_value=1.0,
        value=float(probability),
        step=0.05,
        format="%.4f",
        key=f"probability_{index}",
    )
    updated_events.append((formula, probability))
st.session_state.events = updated_events
left, right = st.columns([1, 1])
left.button("Add event", on_click=_add_event)
right.button("Remove last event", on_click=_remove_event)

st.subheader("3. Logical relations")
st.text_area(
    "One relation per line",
    key="relations",
    height=90,
    help="Use and, or, not, and parentheses. Example: not (A and B)",
)

if st.button("Check coherence", type="primary"):
    try:
        events = [
            Event(formula, probability)
            for formula, probability in st.session_state.events
        ]
        relations = tuple(
            relation.strip()
            for relation in st.session_state.relations.splitlines()
            if relation.strip()
        )
        _render_result(check_coherence(events, relations))
    except Exception as error:
        st.error(f"Input error: {error}")

st.subheader("4. Extend the assessment to one additional event")
st.write(
    "Enter a new unconditional event F. The app computes all values z=P(F) "
    "that preserve coherence of the original assessment."
)
st.text_input(
    "New event F",
    value="C",
    key="extension_target",
    help="Use the same Boolean syntax as for the assessed events.",
)
if st.button("Compute coherent extension"):
    try:
        events = [
            Event(formula, probability)
            for formula, probability in st.session_state.events
        ]
        relations = tuple(
            relation.strip()
            for relation in st.session_state.relations.splitlines()
            if relation.strip()
        )
        extension = coherent_extension_interval(
            events,
            st.session_state.extension_target,
            relations,
        )
        _render_extension(extension)
    except Exception as error:
        st.error(f"Extension error: {error}")

st.caption(
    "Boolean syntax: and, or, not, parentheses. Empty formulas are interpreted as True."
)
