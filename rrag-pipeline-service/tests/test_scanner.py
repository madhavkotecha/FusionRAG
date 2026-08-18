"""Tests for the ComponentScanner AST-based scanner."""

import pytest
from textwrap import dedent

from pipeline_service.framework.scanner import ComponentScanner


@pytest.fixture
def scanner():
    return ComponentScanner()


class TestScanSourceBasic:
    """Test scanning valid source code with @component and @step."""

    def test_scan_component_with_steps(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="retriever", name="Smart Retriever", description="A smart retriever")
            class SmartRetriever(CompositeComponent):
                @step(order=1, name="Retrieve")
                async def retrieve(self, data, config):
                    return data

                @step(order=2, name="Rerank")
                async def rerank(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)

        assert meta is not None
        assert meta["category"] == "retriever"
        assert meta["name"] == "Smart Retriever"
        assert meta["description"] == "A smart retriever"
        assert meta["is_composite"] is True
        assert len(meta["steps"]) == 2
        assert meta["type"] == "smart_retriever"

    def test_extract_step_details(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="composite", name="Test")
            class TestComp(CompositeComponent):
                @step(order=1, name="Validate", retry=2, retry_condition="needs_retry")
                async def validate(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)
        step = meta["steps"][0]

        assert step["order"] == 1
        assert step["name"] == "Validate"
        assert step["method"] == "validate"
        assert step["retry"] == 2
        assert step["retry_condition"] == "needs_retry"

    def test_step_outputs_extraction(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="composite", name="Test")
            class TestComp(CompositeComponent):
                @step(order=1, name="Eval", outputs=["refine", "done"])
                async def evaluate(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)
        step = meta["steps"][0]

        assert step["outputs"] == ["refine", "done"]

    def test_steps_sorted_by_order(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="composite", name="Test")
            class TestComp(CompositeComponent):
                @step(order=3, name="Third")
                async def third(self, data, config):
                    return data

                @step(order=1, name="First")
                async def first(self, data, config):
                    return data

                @step(order=2, name="Second")
                async def second(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)

        assert meta["steps"][0]["name"] == "First"
        assert meta["steps"][1]["name"] == "Second"
        assert meta["steps"][2]["name"] == "Third"


class TestScanSourceConfigSchema:
    """Test CONFIG_SCHEMA class attribute fallback."""

    def test_config_schema_from_class_attribute(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="retriever", name="Test")
            class TestComp(CompositeComponent):
                CONFIG_SCHEMA = {"top_k": {"type": "integer", "default": 5}}

                @step(order=1)
                async def retrieve(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)

        assert meta["config_schema"] == {"top_k": {"type": "integer", "default": 5}}

    def test_decorator_config_schema_takes_precedence(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="retriever", name="Test", config_schema={"model": "gpt-4"})
            class TestComp(CompositeComponent):
                CONFIG_SCHEMA = {"top_k": 5}

                @step(order=1)
                async def retrieve(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)

        assert meta["config_schema"] == {"model": "gpt-4"}


class TestScanSourceEdgeCases:
    """Test edge cases and error handling."""

    def test_no_component_returns_none(self, scanner):
        source = dedent("""\
            class PlainClass:
                def method(self):
                    pass
        """)

        assert scanner.scan_source(source) is None

    def test_invalid_python_raises_syntax_error(self, scanner):
        source = "def broken(:\n    pass"

        with pytest.raises(SyntaxError):
            scanner.scan_source(source)

    def test_step_auto_name_from_method(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component, step, CompositeComponent

            @component(category="composite", name="Test")
            class TestComp(CompositeComponent):
                @step(order=1)
                async def do_something_cool(self, data, config):
                    return data
        """)

        meta = scanner.scan_source(source)
        step = meta["steps"][0]

        assert step["name"] == "Do Something Cool"
        assert step["method"] == "do_something_cool"

    def test_component_without_steps_not_composite(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component

            @component(category="retriever", name="Simple")
            class SimpleRetriever:
                pass
        """)

        meta = scanner.scan_source(source)

        assert meta is not None
        assert meta["is_composite"] is False
        assert meta["steps"] == []


class TestSnakeCaseConversion:
    """Test type derivation from class name."""

    def test_simple_camel_case(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component

            @component(category="retriever", name="Test")
            class BasicRetriever:
                pass
        """)

        meta = scanner.scan_source(source)
        assert meta["type"] == "basic_retriever"

    def test_acronym_handling(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component

            @component(category="retriever", name="Test")
            class LightRAGRetrieval:
                pass
        """)

        meta = scanner.scan_source(source)
        assert meta["type"] == "lightrag_retrieval"

    def test_single_word(self, scanner):
        source = dedent("""\
            from pipeline_service.framework import component

            @component(category="retriever", name="Test")
            class Retriever:
                pass
        """)

        meta = scanner.scan_source(source)
        assert meta["type"] == "retriever"
