from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class ComponentScanner:
    """Scans Python files for @component/@step decorators using AST.

    Never executes user code during scanning.
    """

    def scan_source(self, source_code: str) -> dict[str, Any] | None:
        """Parse source code and extract component metadata.

        Returns metadata dict or None if no @component class found.
        Raises SyntaxError if source is not valid Python.
        """
        tree = ast.parse(source_code)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                comp_meta = self._extract_component_decorator(node)
                if comp_meta is not None:
                    steps = self._extract_steps(node)
                    comp_meta["steps"] = sorted(steps, key=lambda s: s["order"])
                    comp_meta["is_composite"] = len(steps) > 0

                    if comp_meta["config_schema"] is None:
                        class_schema = self._extract_class_attribute(
                            node, "CONFIG_SCHEMA"
                        )
                        if class_schema is not None:
                            comp_meta["config_schema"] = class_schema

                    comp_meta["type"] = self._to_snake_case(node.name)
                    return comp_meta

        return None

    def scan_file(self, file_path: Path) -> dict[str, Any] | None:
        source = file_path.read_text(encoding="utf-8")
        return self.scan_source(source)

    def scan_directory(self, dir_path: Path) -> list[dict[str, Any]]:
        results = []
        for py_file in dir_path.glob("*.py"):
            try:
                meta = self.scan_file(py_file)
                if meta is not None:
                    results.append(meta)
            except SyntaxError:
                continue
        return results

    def _extract_component_decorator(
        self, class_node: ast.ClassDef
    ) -> dict[str, Any] | None:
        for dec in class_node.decorator_list:
            if isinstance(dec, ast.Call):
                func = dec.func
                dec_name = None
                if isinstance(func, ast.Name):
                    dec_name = func.id
                elif isinstance(func, ast.Attribute):
                    dec_name = func.attr

                if dec_name == "component":
                    return self._extract_kwargs(
                        dec,
                        {
                            "category": None,
                            "name": None,
                            "description": "",
                            "config_schema": None,
                            "input_ports": None,
                            "output_ports": None,
                        },
                    )
        return None

    def _extract_steps(self, class_node: ast.ClassDef) -> list[dict[str, Any]]:
        steps = []
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in item.decorator_list:
                    if isinstance(dec, ast.Call):
                        func = dec.func
                        dec_name = None
                        if isinstance(func, ast.Name):
                            dec_name = func.id
                        elif isinstance(func, ast.Attribute):
                            dec_name = func.attr

                        if dec_name == "step":
                            step_meta = self._extract_kwargs(
                                dec,
                                {
                                    "order": 0,
                                    "name": None,
                                    "description": "",
                                    "retry": 0,
                                    "retry_condition": None,
                                    "outputs": None,
                                    "config_schema": None,
                                },
                            )
                            step_meta["method"] = item.name
                            if step_meta["name"] is None:
                                step_meta["name"] = (
                                    item.name.replace("_", " ").title()
                                )
                            steps.append(step_meta)
        return steps

    def _extract_class_attribute(
        self, class_node: ast.ClassDef, attr_name: str
    ) -> Any:
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return self._eval_literal(item.value)
        return None

    def _extract_kwargs(
        self, call_node: ast.Call, defaults: dict[str, Any]
    ) -> dict[str, Any]:
        result = dict(defaults)
        param_order = list(defaults.keys())
        for i, arg in enumerate(call_node.args):
            if i < len(param_order):
                result[param_order[i]] = self._eval_literal(arg)
        for kw in call_node.keywords:
            if kw.arg in result or kw.arg is not None:
                result[kw.arg] = self._eval_literal(kw.value)
        return result

    def _eval_literal(self, node: ast.expr) -> Any:
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_snake_case(name: str) -> str:
        s1 = re.sub(r"([a-z0-9])([A-Z][a-z])", r"\1_\2", name)
        s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
        return s2.lower()
