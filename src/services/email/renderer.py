from typing import Any, Dict, Iterable, Mapping

from jinja2.sandbox import SandboxedEnvironment

_ENV = SandboxedEnvironment(autoescape=True)


def _sanitize_context(context: Mapping[str, Any], allowed: Iterable[str]) -> Dict[str, str]:
    allowed_set = set(allowed)
    cleaned: Dict[str, str] = {key: "" for key in allowed_set}
    for key, value in context.items():
        if key not in allowed_set:
            continue
        cleaned[key] = "" if value is None else str(value)
    return cleaned


def render_template_string(template: str, context: Mapping[str, Any], allowed: Iterable[str]) -> str:
    compiled = _ENV.from_string(template or "")
    return compiled.render(**_sanitize_context(context, allowed))
