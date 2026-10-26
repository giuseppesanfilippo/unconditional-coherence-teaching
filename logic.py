"""Small, didactic implementation of coherence for unconditional events."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class Event:
    formula: str
    probability: float


@dataclass(frozen=True)
class Constituent:
    statuses: tuple[bool, ...]
    witnesses: tuple[dict[str, bool], ...]

    @property
    def q(self) -> np.ndarray:
        return np.asarray(self.statuses, dtype=float)


@dataclass(frozen=True)
class CoherenceResult:
    coherent: bool
    constituents: tuple[Constituent, ...]
    lambda_solution: np.ndarray | None
    message: str


@dataclass(frozen=True)
class ExtensionResult:
    lower: float
    upper: float
    constituents: tuple[Constituent, ...]
    lower_lambda: np.ndarray
    upper_lambda: np.ndarray


def _parse(formula: str) -> ast.AST:
    formula = formula.strip() or "True"
    try:
        tree = ast.parse(formula, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"Invalid Boolean formula {formula!r}.") from exc
    allowed = (
        ast.Name, ast.Constant, ast.BoolOp, ast.And, ast.Or,
        ast.UnaryOp, ast.Not, ast.Load,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError(
            f"Unsupported syntax in {formula!r}. Use and, or, not, and parentheses."
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            raise ValueError(f"Only Boolean constants are allowed in {formula!r}.")
    return tree


def _names(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def _evaluate(tree: ast.AST, environment: Mapping[str, bool]) -> bool:
    if isinstance(tree, ast.Name):
        return bool(environment[tree.id])
    if isinstance(tree, ast.Constant):
        return bool(tree.value)
    if isinstance(tree, ast.BoolOp):
        values = [_evaluate(value, environment) for value in tree.values]
        return all(values) if isinstance(tree.op, ast.And) else any(values)
    if isinstance(tree, ast.UnaryOp) and isinstance(tree.op, ast.Not):
        return not _evaluate(tree.operand, environment)
    raise TypeError(f"Unsupported syntax node: {type(tree).__name__}")


def build_constituents(
    events: Sequence[Event], relations: Sequence[str] = ()
) -> tuple[Constituent, ...]:
    """Enumerate atoms and merge atoms with the same event truth pattern."""
    if not events:
        raise ValueError("Enter at least one event.")

    event_trees = [_parse(event.formula) for event in events]
    relation_trees = [_parse(relation) for relation in relations if relation.strip()]
    symbols: set[str] = set()
    for tree in event_trees + relation_trees:
        symbols |= _names(tree)

    groups: dict[tuple[bool, ...], list[dict[str, bool]]] = {}
    for values in product((False, True), repeat=len(symbols)):
        environment = dict(zip(sorted(symbols), values))
        if not all(_evaluate(tree, environment) for tree in relation_trees):
            continue
        pattern = tuple(_evaluate(tree, environment) for tree in event_trees)
        groups.setdefault(pattern, []).append(environment)

    return tuple(
        Constituent(statuses=pattern, witnesses=tuple(witnesses))
        for pattern, witnesses in groups.items()
    )


def check_coherence(
    events: Sequence[Event], relations: Sequence[str] = ()
) -> CoherenceResult:
    """Check whether p is a convex combination of the constituent points."""
    for event in events:
        if not 0.0 <= event.probability <= 1.0:
            raise ValueError("Every probability must lie between 0 and 1.")

    constituents = build_constituents(events, relations)
    if not constituents:
        return CoherenceResult(
            coherent=False,
            constituents=(),
            lambda_solution=None,
            message="The logical relations admit no possible world.",
        )

    Q = np.vstack([constituent.q for constituent in constituents])
    p = np.asarray([event.probability for event in events], dtype=float)
    A_eq = np.vstack([Q.T, np.ones(len(constituents))])
    b_eq = np.concatenate([p, [1.0]])
    solution = linprog(
        c=np.zeros(len(constituents)),
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=[(0.0, None)] * len(constituents),
        method="highs",
    )
    if solution.success and solution.x is not None:
        return CoherenceResult(
            coherent=True,
            constituents=constituents,
            lambda_solution=solution.x,
            message="The assessment is coherent: p belongs to the convex hull of the constituent points.",
        )
    return CoherenceResult(
        coherent=False,
        constituents=constituents,
        lambda_solution=None,
        message="The assessment is incoherent: p does not belong to the convex hull of the constituent points.",
    )


def coherent_extension_interval(
    events: Sequence[Event],
    target: str,
    relations: Sequence[str] = (),
) -> ExtensionResult:
    """Compute the coherent interval for one additional unconditional event.

    The target is appended to the assessment with an unknown probability z.
    If q_k is the point of a constituent for the enlarged family, then
    z = sum_k lambda_k q_{k,target}.  We minimize and maximize this quantity
    subject to the original assessment equations and sum(lambda)=1.
    """
    base_result = check_coherence(events, relations)
    if not base_result.coherent:
        raise ValueError(
            "A coherent extension can be computed only from a coherent assessment."
        )

    enlarged_events = list(events) + [Event(target, 0.0)]
    constituents = build_constituents(enlarged_events, relations)
    if not constituents:
        raise ValueError("The logical relations admit no possible constituent.")

    Q = np.vstack([constituent.q for constituent in constituents])
    p = np.asarray([event.probability for event in events], dtype=float)
    A_eq = np.vstack([Q[:, :-1].T, np.ones(len(constituents))])
    b_eq = np.concatenate([p, [1.0]])
    target_values = Q[:, -1]

    lower_solution = linprog(
        c=target_values,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=[(0.0, None)] * len(constituents),
        method="highs",
    )
    upper_solution = linprog(
        c=-target_values,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=[(0.0, None)] * len(constituents),
        method="highs",
    )
    if (
        not lower_solution.success
        or lower_solution.x is None
        or not upper_solution.success
        or upper_solution.x is None
    ):
        raise ValueError("The extension optimization problem is infeasible.")

    return ExtensionResult(
        lower=float(lower_solution.fun),
        upper=float(-upper_solution.fun),
        constituents=constituents,
        lower_lambda=lower_solution.x,
        upper_lambda=upper_solution.x,
    )
