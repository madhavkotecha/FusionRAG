"""Tests for CompositeComponent (step runner) execution."""

import pytest

from pipeline_service.components.base import BaseComponent
from pipeline_service.framework.decorators import component, step
from pipeline_service.framework.base import CompositeComponent, StepContext


class TestCompositeComponentInheritance:
    """Verify CompositeComponent is a proper BaseComponent subclass."""

    def test_inherits_from_base_component(self):
        assert issubclass(CompositeComponent, BaseComponent)


class TestStepContext:
    """Tests for the StepContext data carrier."""

    def test_initial_state(self):
        ctx = StepContext(input_data={"query": "hello"}, config={"k": 5})
        assert ctx.current_data == {"query": "hello"}
        assert ctx.step_results == {}
        assert ctx.route is None
        assert ctx.iteration == 0

    def test_update_merges_data(self):
        ctx = StepContext(input_data={"query": "hello"}, config={})
        ctx.update("step_one", {"documents": ["doc1"]})
        assert ctx.current_data == {"query": "hello", "documents": ["doc1"]}
        assert ctx.step_results["step_one"] == {"documents": ["doc1"]}

    def test_final_output_returns_current_data(self):
        ctx = StepContext(input_data={"a": 1}, config={})
        ctx.update("s1", {"b": 2})
        assert ctx.final_output == {"a": 1, "b": 2}


class TestCompositeExecuteStepsInOrder:
    """Test that execute() runs steps sequentially, passing data between them."""

    async def test_two_step_pipeline(self):
        @component(category="composite", name="TwoStep")
        class TwoStep(CompositeComponent):
            @step(order=1, name="Retrieve")
            async def retrieve(self, data, config):
                return {"documents": ["doc1", "doc2"]}

            @step(order=2, name="Generate")
            async def generate(self, data, config):
                docs = data.get("documents", [])
                return {"answer": f"Based on {len(docs)} docs"}

        comp = TwoStep()
        result = await comp.execute({"query": "test"}, {})

        assert result["query"] == "test"
        assert result["documents"] == ["doc1", "doc2"]
        assert result["answer"] == "Based on 2 docs"

    async def test_three_step_pipeline_ordering(self):
        call_order = []

        @component(category="composite", name="ThreeStep")
        class ThreeStep(CompositeComponent):
            @step(order=3)
            async def finalize(self, data, config):
                call_order.append("finalize")
                return {"final": True}

            @step(order=1)
            async def start(self, data, config):
                call_order.append("start")
                return {"started": True}

            @step(order=2)
            async def middle(self, data, config):
                call_order.append("middle")
                return {"midway": True}

        comp = ThreeStep()
        result = await comp.execute({}, {})

        assert call_order == ["start", "middle", "finalize"]
        assert result["started"] is True
        assert result["midway"] is True
        assert result["final"] is True


class TestCompositeRetryBehavior:
    """Test retry logic in step execution."""

    async def test_retry_on_condition(self):
        attempt_count = 0

        @component(category="composite", name="RetryTest")
        class RetryTest(CompositeComponent):
            @step(order=1, retry=3, retry_condition="needs_retry")
            async def flaky(self, data, config):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count < 3:
                    return {"needs_retry": True, "attempt": attempt_count}
                return {"needs_retry": False, "attempt": attempt_count}

        comp = RetryTest()
        result = await comp.execute({}, {})

        assert attempt_count == 3
        assert result["needs_retry"] is False
        assert result["attempt"] == 3

    async def test_no_retry_when_condition_immediately_false(self):
        attempt_count = 0

        @component(category="composite", name="NoRetry")
        class NoRetry(CompositeComponent):
            @step(order=1, retry=5, retry_condition="needs_retry")
            async def stable(self, data, config):
                nonlocal attempt_count
                attempt_count += 1
                return {"needs_retry": False, "value": "ok"}

        comp = NoRetry()
        result = await comp.execute({}, {})

        assert attempt_count == 1
        assert result["value"] == "ok"

    async def test_retry_exhausted(self):
        """When all retries are used and condition is still true."""
        attempt_count = 0

        @component(category="composite", name="AlwaysFail")
        class AlwaysFail(CompositeComponent):
            @step(order=1, retry=2, retry_condition="needs_retry")
            async def always_retry(self, data, config):
                nonlocal attempt_count
                attempt_count += 1
                return {"needs_retry": True, "attempt": attempt_count}

        comp = AlwaysFail()
        result = await comp.execute({}, {})

        # retry=2 means 3 total attempts (1 original + 2 retries)
        assert attempt_count == 3
        assert result["needs_retry"] is True


class TestCompositeRouting:
    """Test back-edge routing between steps."""

    async def test_back_edge_routing(self):
        """Step with outputs can route back to an earlier step."""
        loop_count = 0

        @component(category="composite", name="LoopingPipeline")
        class LoopingPipeline(CompositeComponent):
            @step(order=1, name="Retrieve")
            async def retrieve(self, data, config):
                return {"documents": ["doc1"]}

            @step(order=2, name="Evaluate", outputs=["Retrieve", "done"])
            async def evaluate(self, data, config):
                nonlocal loop_count
                loop_count += 1
                if loop_count < 2:
                    return {"_route": "Retrieve", "score": 0.3}
                return {"_route": "done", "score": 0.9}

        comp = LoopingPipeline()
        result = await comp.execute({"query": "test"}, {})

        assert loop_count == 2
        assert result["score"] == 0.9

    async def test_max_iterations_prevents_infinite_loop(self):
        loop_count = 0

        @component(category="composite", name="InfiniteLoop")
        class InfiniteLoop(CompositeComponent):
            @step(order=1, name="Start")
            async def start(self, data, config):
                return {"started": True}

            @step(order=2, name="Loop", outputs=["Start", "done"])
            async def loop(self, data, config):
                nonlocal loop_count
                loop_count += 1
                # Always routes back, never "done"
                return {"_route": "Start", "looped": loop_count}

        comp = InfiniteLoop()
        result = await comp.execute({}, {"max_iterations": 3})

        # Should stop after 3 iterations, not run forever
        assert loop_count <= 3
        assert result["started"] is True

    async def test_default_route_is_first_output(self):
        """When _route is not in result, uses first output as default."""
        loop_count = 0

        @component(category="composite", name="DefaultRoute")
        class DefaultRoute(CompositeComponent):
            @step(order=1, name="Process")
            async def process(self, data, config):
                return {"processed": True}

            @step(order=2, name="Check", outputs=["Process", "done"])
            async def check(self, data, config):
                nonlocal loop_count
                loop_count += 1
                # No _route key, so it defaults to first output "Process"
                if loop_count < 2:
                    return {"checked": True}
                return {"_route": "done", "checked": True}

        comp = DefaultRoute()
        result = await comp.execute({}, {})

        assert loop_count == 2


class TestCompositeErrorHandling:
    """Test error handling in execute()."""

    async def test_no_component_meta_raises_runtime_error(self):
        class BareComposite(CompositeComponent):
            pass

        comp = BareComposite()
        with pytest.raises(RuntimeError, match="has no _component_meta"):
            await comp.execute({}, {})

    async def test_empty_steps_raises_runtime_error(self):
        @component(category="test", name="NoSteps")
        class NoSteps(CompositeComponent):
            pass

        comp = NoSteps()
        with pytest.raises(RuntimeError, match="has no _component_meta with steps"):
            await comp.execute({}, {})
