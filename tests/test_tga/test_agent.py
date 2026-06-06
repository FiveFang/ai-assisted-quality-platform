from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from qa_platform.agents.test_generation.agent import TestGenerationAgent
from qa_platform.schemas.test_cases import TestCase, TestStep, TestSuite


class TestTestGenerationAgent:
    @pytest.mark.asyncio
    async def test_process_returns_test_suite(self, sample_normalized) -> None:
        agent = TestGenerationAgent()

        stub_cases_raw = [{
            "source_requirement_id": "REQ-001",
            "type": "FUNCTIONAL",
            "title": "Test case",
            "description": "desc",
            "steps": [{"step_number": 1, "action": "do thing", "expected_result": "thing done"}],
            "expected_results": ["thing done"],
            "tags": ["functional", "positive"],
        }]

        stub_test_case = TestCase(
            source_requirement_id="REQ-001",
            type="FUNCTIONAL",
            priority="P1",
            title="Test case",
            description="desc",
            steps=[TestStep(step_number=1, action="do thing", expected_result="thing done")],
            expected_results=["thing done"],
        )

        with (
            patch.object(agent._functional, "execute", new_callable=AsyncMock, return_value=stub_cases_raw),
            patch.object(agent._api, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._security, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._mobile_ui, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._assertion_gen, "execute", new_callable=AsyncMock, return_value=stub_cases_raw),
            patch.object(agent._deduplicator, "execute", new_callable=AsyncMock, return_value=stub_cases_raw),
            patch.object(agent._prioritizer, "execute", new_callable=AsyncMock, return_value=stub_cases_raw),
            patch.object(agent._formatter, "execute", new_callable=AsyncMock, return_value=[stub_test_case]),
            patch.object(agent._scaffold_gen, "execute", new_callable=AsyncMock, return_value=[stub_test_case]),
        ):
            result = await agent.process(sample_normalized)

            assert isinstance(result, TestSuite)
            assert result.source_requirement_id == sample_normalized.requirement_id
            assert result.metadata.total_test_cases == 1
            assert len(result.test_cases) == 1

    @pytest.mark.asyncio
    async def test_process_empty_contracts_skips_api_generation(self, sample_normalized) -> None:
        """When there are no API contracts, API generator should be called with empty list."""
        agent = TestGenerationAgent()

        with (
            patch.object(agent._functional, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._api, "execute", new_callable=AsyncMock, return_value=[]) as mock_api,
            patch.object(agent._security, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._mobile_ui, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._assertion_gen, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._deduplicator, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._prioritizer, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._formatter, "execute", new_callable=AsyncMock, return_value=[]),
            patch.object(agent._scaffold_gen, "execute", new_callable=AsyncMock, return_value=[]),
        ):
            result = await agent.process(sample_normalized)
            mock_api.assert_called_once_with([])
            assert result.metadata.total_test_cases == 0

    def test_estimate_coverage_full(self, sample_normalized) -> None:
        agent = TestGenerationAgent()
        requirements = [r.model_dump() for r in sample_normalized.requirements]
        test_cases = [
            TestCase(
                source_requirement_id="REQ-001",
                type="FUNCTIONAL",
                title="t",
                description="d",
                steps=[],
                expected_results=[],
            )
        ]
        coverage = agent._estimate_coverage(test_cases, requirements)
        assert coverage == 1.0

    def test_estimate_coverage_zero_requirements(self, sample_normalized) -> None:
        agent = TestGenerationAgent()
        coverage = agent._estimate_coverage([], [])
        assert coverage == 0.0
