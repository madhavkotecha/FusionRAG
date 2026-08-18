"""Tests for @component and @step decorators."""

import pytest

from pipeline_service.framework.decorators import component, step, _to_snake_case


class TestStepDecorator:
    """Tests for the @step method decorator."""

    def test_step_attaches_metadata(self):
        @step(order=1, name="Retrieve")
        async def retrieve(self, data, config):
            return data

        assert hasattr(retrieve, "_step_meta")
        assert retrieve._step_meta["order"] == 1
        assert retrieve._step_meta["name"] == "Retrieve"
        assert retrieve._step_meta["method"] == "retrieve"

    def test_step_defaults(self):
        @step(order=2)
        async def do_something(self, data, config):
            return data

        meta = do_something._step_meta
        assert meta["order"] == 2
        assert meta["name"] == "Do Something"  # auto-derived from method name
        assert meta["description"] == ""
        assert meta["retry"] == 0
        assert meta["retry_condition"] is None
        assert meta["outputs"] is None
        assert meta["config_schema"] is None

    def test_step_retry_config(self):
        @step(order=1, retry=3, retry_condition="needs_retry")
        async def flaky_step(self, data, config):
            return data

        meta = flaky_step._step_meta
        assert meta["retry"] == 3
        assert meta["retry_condition"] == "needs_retry"

    def test_step_outputs_for_routing(self):
        @step(order=1, outputs=["refine", "done"])
        async def evaluate(self, data, config):
            return data

        meta = evaluate._step_meta
        assert meta["outputs"] == ["refine", "done"]

    def test_step_config_schema(self):
        schema = {"top_k": {"type": "integer", "default": 5}}

        @step(order=1, config_schema=schema)
        async def retrieve(self, data, config):
            return data

        assert retrieve._step_meta["config_schema"] == schema

    def test_step_preserves_function_behavior(self):
        @step(order=1)
        async def my_step(self, data, config):
            return {"result": "ok"}

        # The function should still be callable (it's the same function)
        assert callable(my_step)
        assert my_step.__name__ == "my_step"


class TestComponentDecorator:
    """Tests for the @component class decorator."""

    def test_component_attaches_metadata(self):
        @component(category="retriever", name="Basic Retriever")
        class BasicRetriever:
            pass

        assert hasattr(BasicRetriever, "_component_meta")
        meta = BasicRetriever._component_meta
        assert meta["category"] == "retriever"
        assert meta["name"] == "Basic Retriever"

    def test_component_default_values(self):
        @component(category="retriever", name="Test")
        class TestComp:
            pass

        meta = TestComp._component_meta
        assert meta["description"] == ""
        assert meta["config_schema"] is None
        assert meta["input_ports"] is None
        assert meta["output_ports"] is None
        assert meta["is_composite"] is False
        assert meta["steps"] == []

    def test_component_preserves_class_behavior(self):
        @component(category="retriever", name="Test")
        class MyClass:
            def __init__(self):
                self.value = 42

            def get_value(self):
                return self.value

        obj = MyClass()
        assert obj.get_value() == 42

    def test_component_config_schema_passthrough(self):
        schema = {"model": {"type": "string"}}

        @component(category="generator", name="Gen", config_schema=schema)
        class Gen:
            pass

        assert Gen._component_meta["config_schema"] == schema

    def test_component_ports_passthrough(self):
        inputs = [{"name": "query", "type": "string"}]
        outputs = [{"name": "results", "type": "list"}]

        @component(
            category="retriever",
            name="Test",
            input_ports=inputs,
            output_ports=outputs,
        )
        class TestComp:
            pass

        assert TestComp._component_meta["input_ports"] == inputs
        assert TestComp._component_meta["output_ports"] == outputs

    def test_component_collects_steps_sorted_by_order(self):
        @component(category="composite", name="Multi Step")
        class MultiStep:
            @step(order=3)
            async def third(self, data, config):
                return data

            @step(order=1)
            async def first(self, data, config):
                return data

            @step(order=2)
            async def second(self, data, config):
                return data

        meta = MultiStep._component_meta
        assert meta["is_composite"] is True
        assert len(meta["steps"]) == 3
        assert meta["steps"][0]["method"] == "first"
        assert meta["steps"][1]["method"] == "second"
        assert meta["steps"][2]["method"] == "third"

    def test_config_schema_class_attribute_fallback(self):
        @component(category="retriever", name="Test")
        class WithClassSchema:
            CONFIG_SCHEMA = {"top_k": {"type": "integer"}}

        assert WithClassSchema._component_meta["config_schema"] == {
            "top_k": {"type": "integer"}
        }

    def test_decorator_config_schema_overrides_class_attribute(self):
        decorator_schema = {"model": {"type": "string"}}

        @component(
            category="retriever", name="Test", config_schema=decorator_schema
        )
        class WithBothSchemas:
            CONFIG_SCHEMA = {"top_k": {"type": "integer"}}

        # Decorator-provided config_schema takes precedence
        assert WithBothSchemas._component_meta["config_schema"] == decorator_schema

    def test_component_type_derived_from_class_name(self):
        @component(category="retriever", name="Test")
        class LightRAGRetrieval:
            pass

        assert LightRAGRetrieval._component_type == "lightrag_retrieval"

    def test_component_type_simple_class(self):
        @component(category="retriever", name="Test")
        class BasicRetriever:
            pass

        assert BasicRetriever._component_type == "basic_retriever"

    def test_component_does_not_overwrite_existing_component_type(self):
        @component(category="retriever", name="Test")
        class MyComp:
            _component_type = "custom_type"

        assert MyComp._component_type == "custom_type"


class TestToSnakeCase:
    """Tests for the _to_snake_case utility."""

    def test_simple_camel_case(self):
        assert _to_snake_case("BasicRetriever") == "basic_retriever"

    def test_acronym_handling(self):
        assert _to_snake_case("LightRAGRetrieval") == "lightrag_retrieval"

    def test_single_word(self):
        assert _to_snake_case("Component") == "component"

    def test_already_lowercase(self):
        assert _to_snake_case("component") == "component"

    def test_multiple_acronyms(self):
        assert _to_snake_case("HTTPAPIClient") == "httpapi_client"

    def test_digit_boundary(self):
        assert _to_snake_case("Step2Retriever") == "step2_retriever"
