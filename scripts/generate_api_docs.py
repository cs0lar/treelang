"""Generate deterministic Markdown documentation for Treelang's public API."""

from __future__ import annotations

import argparse
import inspect
import types
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, ForwardRef, Literal, Union, get_args, get_origin

import treelang

ROOT = Path(__file__).parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "api.md"


class _RenderedAnnotation:
    """Annotation wrapper whose representation is independent of Python."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __repr__(self) -> str:
        return _annotation(self.value)


def _annotation(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return f"[{', '.join(_annotation(item) for item in value)}]"
    if isinstance(value, ForwardRef):
        return value.__forward_arg__
    if value is Ellipsis:
        return "..."
    if value is None or value is type(None):
        return "None"

    origin = get_origin(value)
    arguments = get_args(value)
    if origin in (Union, types.UnionType):
        return " | ".join(_annotation(argument) for argument in arguments)
    if origin is Annotated:
        base, *metadata = arguments
        rendered_metadata = ", ".join(repr(item) for item in metadata)
        return f"Annotated[{_annotation(base)}, {rendered_metadata}]"
    if origin is Literal:
        return f"Literal[{', '.join(repr(item) for item in arguments)}]"
    if origin is not None:
        rendered_origin = (
            "Callable" if origin is Callable else inspect.formatannotation(origin)
        ).replace("typing.", "")
        return (
            f"{rendered_origin}[{', '.join(_annotation(item) for item in arguments)}]"
        )
    return inspect.formatannotation(value).replace("typing.", "")


def _signature(value: Any) -> str:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return ""

    parameters = [
        parameter.replace(
            annotation=_RenderedAnnotation(parameter.annotation)
            if parameter.annotation is not inspect.Parameter.empty
            else inspect.Parameter.empty
        )
        for parameter in signature.parameters.values()
    ]
    return_annotation = signature.return_annotation
    if return_annotation is not inspect.Signature.empty:
        return_annotation = _RenderedAnnotation(return_annotation)
    return str(
        signature.replace(
            parameters=parameters,
            return_annotation=return_annotation,
        )
    )


def _kind(value: Any) -> str:
    if inspect.isclass(value):
        if hasattr(value, "__required_keys__"):
            return "Typed dictionary"
        return "Class"
    if inspect.isfunction(value):
        return "Function"
    return "Constant"


def _class_members(value: type[Any]) -> list[str]:
    lines: list[str] = []
    fields = getattr(value, "model_fields", None)
    annotations = getattr(value, "__annotations__", {})
    if fields or (hasattr(value, "__required_keys__") and annotations):
        lines.extend(["", "Fields:", ""])
        field_names = fields if fields else annotations
        for name in field_names:
            annotation = annotations.get(name, Any)
            lines.append(f"- `{name}: {_annotation(annotation)}`")

    methods: list[tuple[str, Any]] = []
    for name, member in value.__dict__.items():
        if name.startswith("_"):
            continue
        if isinstance(member, (classmethod, staticmethod)):
            member = member.__func__
        if inspect.isfunction(member):
            methods.append((name, member))
    if methods:
        lines.extend(["", "Methods:", ""])
        for name, member in methods:
            docstring = inspect.getdoc(member)
            summary = docstring.splitlines()[0] if docstring else ""
            description = f" — {summary}" if summary else ""
            lines.append(f"- `{name}{_signature(member)}`{description}")
    return lines


def render_api_reference() -> str:
    """Return Markdown for every explicitly supported package export."""
    lines = [
        "# API Reference",
        "",
        "This file is generated from `treelang.__all__`. Do not edit it by hand;",
        "run `make docs` after changing the supported public API.",
        "",
    ]
    for name in treelang.__all__:
        value = getattr(treelang, name)
        signature = _signature(value) if callable(value) else ""
        lines.extend(
            [
                f"## `{name}`",
                "",
                f"**{_kind(value)}** · `{getattr(value, '__module__', 'treelang')}`",
                "",
            ]
        )
        if signature:
            lines.extend(["```python", f"{name}{signature}", "```", ""])
        raw_docstring = getattr(value, "__doc__", None) if callable(value) else None
        docstring = (
            inspect.cleandoc(raw_docstring) if isinstance(raw_docstring, str) else None
        )
        if docstring:
            lines.extend([docstring, ""])
        if inspect.isclass(value):
            lines.extend(_class_members(value))
            if lines[-1] != "":
                lines.append("")
        if not callable(value):
            lines.extend([f"Current value: `{value!r}`", ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    generated = render_api_reference()
    if arguments.check:
        if (
            not arguments.output.exists()
            or arguments.output.read_text(encoding="utf-8") != generated
        ):
            parser.error(
                f"{arguments.output} is stale; run `make docs` and commit the result"
            )
        print(f"API documentation is current: {arguments.output}")
        return 0
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(generated, encoding="utf-8")
    print(f"Generated API documentation: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
