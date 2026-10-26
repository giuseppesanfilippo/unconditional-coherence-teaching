"""Small, didactic implementation of coherence for unconditional events."""

from __future__ import annotations

import ast
import re
from itertools import product
from typing import Mapping, NamedTuple, Sequence

import numpy as np
from scipy.optimize import linprog


class Event(NamedTuple):
    formula: str
    probability: float


class Constituent(NamedTuple):
    statuses: tuple[bool, ...]
    witnesses: tuple[dict[str, bool], ...]

    @property
    def q(self) -> np.ndarray:
        return np.asarray(self.statuses, dtype=float)


class CoherenceResult(NamedTuple):
    coherent: bool
    constituents: tuple[Constituent, ...]
    lambda_solution: np.ndarray | None
    message: str


class ExtensionResult(NamedTuple):
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


def _parse_relation(relation: str) -> ast.AST:
    """Parse a relation, allowing the didactic form ``formula = True/False``."""
    relation = relation.strip()
    match = re.fullmatch(r"(.+?)\s*=\s*(True|False)", relation, flags=re.IGNORECASE)
    if match:
        tree = _parse(match.group(1))
        required_value = match.group(2).lower() == "true"
        if required_value:
            return tree
        return ast.UnaryOp(op=ast.Not(), operand=tree)
    return _parse(relation)


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


def _latex_name(name: str) -> str:
    if "_" in name:
        base, suffix = name.split("_", 1)
        return rf"{base}_{{{suffix}}}"
    return name


def _latex_tree(tree: ast.AST) -> str:
    if isinstance(tree, ast.Name):
        return _latex_name(tree.id)
    if isinstance(tree, ast.Constant):
        return r"\top" if tree.value else r"\bot"
    if isinstance(tree, ast.BoolOp):
        connective = r"\land" if isinstance(tree.op, ast.And) else r"\lor"
        return "(" + f" {connective} ".join(
            _latex_tree(value) for value in tree.values
        ) + ")"
    if isinstance(tree, ast.UnaryOp) and isinstance(tree.op, ast.Not):
        return rf"\overline{{{_latex_tree(tree.operand)}}}"
    raise TypeError(f"Unsupported syntax node: {type(tree).__name__}")


def formula_to_latex(formula: str) -> str:
    """Convert the app's Boolean formula syntax to a compact LaTeX formula."""
    return _latex_tree(_parse(formula))


def _flatten_and(tree: ast.AST) -> list[ast.AST]:
    if isinstance(tree, ast.BoolOp) and isinstance(tree.op, ast.And):
        factors: list[ast.AST] = []
        for value in tree.values:
            factors.extend(_flatten_and(value))
        return factors
    return [tree]


def _factor_key(tree: ast.AST) -> str:
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def _simplify_conjunction(terms: Sequence[ast.AST]) -> ast.AST:
    factors: list[ast.AST] = []
    for term in terms:
        factors.extend(_flatten_and(term))

    unique: dict[str, ast.AST] = {}
    for factor in factors:
        key = _factor_key(factor)
        if key not in unique:
            unique[key] = factor

    factors = list(unique.values())
    symbols = sorted({name for factor in factors for name in _names(factor)})

    def conjunction_is_possible(candidate: Sequence[ast.AST]) -> bool:
        for values in product((False, True), repeat=len(symbols)):
            environment = dict(zip(symbols, values))
            if all(_evaluate(factor, environment) for factor in candidate):
                return True
        return False

    # A and not A would be contradictory. It should not occur for a reachable
    # constituent, but handling it makes the simplifier safe for all inputs.
    if not conjunction_is_possible(factors):
        return ast.Constant(value=False)

    # Remove every factor implied by the remaining factors. This covers exact
    # duplicates, absorption (A and (A or B)), and logical redundancies such as
    # not A and not B and not (A and B).
    changed = True
    while changed and factors:
        changed = False
        # Prefer removing a compound factor before an elementary factor. For
        # example, keep A and not B rather than keeping not B and (A or B).
        candidate_indices = sorted(
            range(len(factors)),
            key=lambda index: len(list(ast.walk(factors[index]))),
            reverse=True,
        )
        for index in candidate_indices:
            factor = factors[index]
            remaining = factors[:index] + factors[index + 1:]
            implied = True
            for values in product((False, True), repeat=len(symbols)):
                environment = dict(zip(symbols, values))
                if all(_evaluate(item, environment) for item in remaining):
                    if not _evaluate(factor, environment):
                        implied = False
                        break
            if implied:
                factors.pop(index)
                changed = True
                break

    if not factors:
        return ast.Constant(value=True)
    if len(factors) == 1:
        return factors[0]
    return ast.BoolOp(op=ast.And(), values=factors)


def constituent_formula_to_latex(
    formulas: Sequence[str], statuses: Sequence[bool]
) -> str:
    """Return a simplified LaTeX formula for one logical constituent."""
    terms = []
    for formula, status in zip(formulas, statuses):
        tree = _parse(formula)
        terms.append(tree if status else ast.UnaryOp(op=ast.Not(), operand=tree))
    return _latex_tree(_simplify_conjunction(terms))


def build_constituents(
    events: Sequence[Event], relations: Sequence[str] = ()
) -> tuple[Constituent, ...]:
    """Enumerate atoms and merge atoms with the same event truth pattern."""
    if not events:
        raise ValueError("Enter at least one event.")

    event_trees = [_parse(event.formula) for event in events]
    relation_trees = [
        _parse_relation(relation) for relation in relations if relation.strip()
    ]
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

    ordered_groups = sorted(
        groups.items(),
        key=lambda item: tuple(not status for status in item[0]),
    )
    return tuple(
        Constituent(statuses=pattern, witnesses=tuple(witnesses))
        for pattern, witnesses in ordered_groups
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
