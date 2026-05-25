"""
Automatic rule discovery and registration.

Uses importlib and pkgutil to scan the ``rules/`` package and discover
all BaseRule subclasses. No manual registration is required — simply
adding a new .py file with a BaseRule subclass to rules/ makes it
available to the engine.

No import-time side effects: discovery only happens when
``discover_rules()`` is explicitly called.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quality.risk.base import BaseRule

logger = logging.getLogger(__name__)


def discover_rules() -> list[BaseRule]:
    """Discover and instantiate all BaseRule subclasses in the rules package.

    Scans ``quality.risk.rules`` for Python modules, imports each one,
    and collects all classes that inherit from BaseRule.

    Returns:
        List of instantiated rule objects, sorted by name.
    """
    from quality.risk.base import BaseRule as _BaseRule

    rules_package_name = "quality.risk.rules"

    try:
        rules_package = importlib.import_module(rules_package_name)
    except ImportError as exc:
        logger.error("Failed to import rules package '%s': %s", rules_package_name, exc)
        return []

    discovered: list[BaseRule] = []

    package_path = getattr(rules_package, "__path__", None)
    if package_path is None:
        logger.error("Rules package '%s' has no __path__", rules_package_name)
        return []

    for module_info in pkgutil.iter_modules(package_path):
        module_name = f"{rules_package_name}.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.warning("Failed to import rule module '%s': %s", module_name, exc)
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, _BaseRule)
                and attr is not _BaseRule
                and hasattr(attr, "name")
                and attr.name  # Skip classes without a name
            ):
                try:
                    instance = attr()
                    discovered.append(instance)
                    logger.debug("Discovered rule: %s", instance.name)
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate rule '%s': %s", attr_name, exc
                    )

    discovered.sort(key=lambda r: r.name)
    logger.info("Discovered %d risk rules", len(discovered))
    return discovered
