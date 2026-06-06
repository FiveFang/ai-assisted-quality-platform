"""
Skill and model routing logic.
Centralizes decisions about which model tier to use for a given task type,
allowing model upgrades/downgrades without touching individual skill files.
"""
from __future__ import annotations

from ..config import ModelTier

_ROUTING_TABLE: dict[str, ModelTier] = {
    # RAA skills
    "PRDParserSkill": ModelTier.BALANCED,
    "JiraParserSkill": ModelTier.FAST,
    "OpenAPIParserSkill": ModelTier.BALANCED,
    "RequirementExtractorSkill": ModelTier.POWERFUL,
    "WorkflowExtractorSkill": ModelTier.BALANCED,
    "RuleExtractorSkill": ModelTier.BALANCED,
    "EntityExtractorSkill": ModelTier.BALANCED,
    "AmbiguityDetectorSkill": ModelTier.BALANCED,
    "RAGEnricherSkill": ModelTier.FAST,
    "ConfidenceScorerSkill": ModelTier.FAST,
    # TGA skills
    "PositiveScenarioSkill": ModelTier.BALANCED,
    "NegativeScenarioSkill": ModelTier.BALANCED,
    "EdgeCaseGeneratorSkill": ModelTier.POWERFUL,
    "APITestGeneratorSkill": ModelTier.BALANCED,
    "SecurityTestGeneratorSkill": ModelTier.BALANCED,
    "MobileUIGeneratorSkill": ModelTier.BALANCED,
    "AssertionGeneratorSkill": ModelTier.FAST,
    "RiskPriorizerSkill": ModelTier.FAST,
    "ScaffoldGeneratorSkill": ModelTier.BALANCED,
}


def get_tier_for_skill(skill_name: str) -> ModelTier:
    """Return the configured model tier for a skill. Falls back to BALANCED."""
    return _ROUTING_TABLE.get(skill_name, ModelTier.BALANCED)
