from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from qa_platform.agents.requirement_analysis.agent import RequirementAnalysisAgent
from qa_platform.schemas.common import ProcessingStatus, SourceType
from qa_platform.schemas.requirements import NormalizedRequirement, RequirementSource


@pytest.fixture
def source() -> RequirementSource:
    return RequirementSource(type=SourceType.PRD, reference="test-prd-001")


@pytest.fixture
def raw_inputs() -> dict:
    return {
        "prd": "Feature: Shopping Cart\n\nUsers can add items to cart.\nAcceptance: Cart count increments."
    }


@pytest.fixture
def mock_extracted_requirements() -> list[dict]:
    return [{
        "requirement_id": "REQ-001",
        "type": "FUNCTIONAL",
        "title": "User can add item to cart",
        "description": "Authenticated users can add in-stock items to cart.",
        "acceptance_criteria": ["Cart count incremented", "Item persists"],
        "priority": "P1",
        "tags": ["cart"],
        "source_reference": "F-001",
    }]


class TestRequirementAnalysisAgent:
    @pytest.mark.asyncio
    async def test_process_returns_normalized_requirement(
        self,
        source: RequirementSource,
        raw_inputs: dict,
        mock_extracted_requirements: list[dict],
    ) -> None:
        agent = RequirementAnalysisAgent()

        with (
            patch.object(agent._prd_parser, "execute", new_callable=AsyncMock) as mock_prd,
            patch.object(agent._req_extractor, "execute", new_callable=AsyncMock) as mock_req,
            patch.object(agent._workflow_extractor, "execute", new_callable=AsyncMock) as mock_wf,
            patch.object(agent._rule_extractor, "execute", new_callable=AsyncMock) as mock_rule,
            patch.object(agent._entity_extractor, "execute", new_callable=AsyncMock) as mock_entity,
            patch.object(agent._rag_enricher, "execute", new_callable=AsyncMock) as mock_rag,
            patch.object(agent._ambiguity_detector, "execute", new_callable=AsyncMock) as mock_amb,
            patch.object(agent._confidence_scorer, "execute", new_callable=AsyncMock) as mock_score,
            patch.object(agent._json_generator, "execute", new_callable=AsyncMock) as mock_json,
        ):
            mock_prd.return_value = {"features": []}
            mock_req.return_value = mock_extracted_requirements
            mock_wf.return_value = []
            mock_rule.return_value = []
            mock_entity.return_value = {"entities": [], "dependencies": []}
            mock_rag.return_value = {"similar_requirements": [], "relevant_domain_knowledge": [], "historical_test_patterns": []}
            mock_amb.return_value = []
            mock_score.return_value = 0.85

            expected = NormalizedRequirement(
                source=source,
                metadata=mock_json.return_value,
                status=ProcessingStatus.APPROVED,
                requirements=[],
            )
            mock_json.return_value = expected

            result = await agent.process(source=source, raw_inputs=raw_inputs)

            assert isinstance(result, NormalizedRequirement)
            mock_prd.assert_called_once()
            mock_req.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_triggers_escalation_on_low_confidence(
        self,
        source: RequirementSource,
        raw_inputs: dict,
        mock_extracted_requirements: list[dict],
    ) -> None:
        agent = RequirementAnalysisAgent()

        with (
            patch.object(agent._prd_parser, "execute", new_callable=AsyncMock) as mock_prd,
            patch.object(agent._req_extractor, "execute", new_callable=AsyncMock) as mock_req,
            patch.object(agent._workflow_extractor, "execute", new_callable=AsyncMock),
            patch.object(agent._rule_extractor, "execute", new_callable=AsyncMock),
            patch.object(agent._entity_extractor, "execute", new_callable=AsyncMock) as mock_entity,
            patch.object(agent._rag_enricher, "execute", new_callable=AsyncMock),
            patch.object(agent._ambiguity_detector, "execute", new_callable=AsyncMock),
            patch.object(agent._confidence_scorer, "execute", new_callable=AsyncMock) as mock_score,
            patch.object(agent._json_generator, "execute", new_callable=AsyncMock) as mock_json,
        ):
            mock_prd.return_value = {"features": []}
            mock_req.return_value = mock_extracted_requirements
            mock_entity.return_value = {"entities": [], "dependencies": []}
            mock_score.return_value = 0.50  # below 0.75 threshold

            low_conf_result = NormalizedRequirement(
                source=source,
                metadata=type("M", (), {"confidence_score": 0.5, "processing_model": "balanced", "skills_executed": []})(),
                status=ProcessingStatus.AWAITING_REVIEW,
                requirements=[],
                human_review_required=True,
            )
            mock_json.return_value = low_conf_result

            result = await agent.process(source=source, raw_inputs=raw_inputs)
            assert result.human_review_required is True

    def test_evaluate_escalation_low_confidence(self) -> None:
        agent = RequirementAnalysisAgent()
        required, reasons = agent._evaluate_escalation(confidence=0.5, ambiguities=[])
        assert required is True
        assert len(reasons) == 1

    def test_evaluate_escalation_blocking_ambiguity(self) -> None:
        agent = RequirementAnalysisAgent()
        ambiguities = [{"severity": "BLOCKING", "blocking": True, "description": "Vague"}]
        required, reasons = agent._evaluate_escalation(confidence=0.9, ambiguities=ambiguities)
        assert required is True

    def test_evaluate_escalation_passes_clean(self) -> None:
        agent = RequirementAnalysisAgent()
        required, reasons = agent._evaluate_escalation(confidence=0.9, ambiguities=[])
        assert required is False
        assert reasons == []

    @pytest.mark.asyncio
    async def test_process_raises_on_empty_inputs(self, source: RequirementSource) -> None:
        agent = RequirementAnalysisAgent()
        with pytest.raises(ValueError, match="raw_inputs must contain"):
            await agent.process(source=source, raw_inputs={})
