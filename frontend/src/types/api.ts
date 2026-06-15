export type ProcessingStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'AWAITING_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED'

export type SourceType = 'PRD' | 'JIRA' | 'OPENAPI' | 'DESIGN_DOC' | 'USER_STORY'
export type RequirementType =
  | 'FUNCTIONAL'
  | 'NON_FUNCTIONAL'
  | 'SECURITY'
  | 'PERFORMANCE'
  | 'ACCESSIBILITY'
export type AmbiguitySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'BLOCKING'

export interface RequirementSource {
  type: SourceType
  reference: string
  url?: string
}

export interface ProcessingMetadata {
  created_at: string
  version: string
  confidence_score: number
  processing_model: string
  skills_executed: string[]
  processing_duration_ms?: number
}

export interface Entity {
  name: string
  type: string
  attributes: string[]
  description?: string
}

export interface WorkflowStep {
  step_id: string
  action: string
  actor: string
  preconditions: string[]
  postconditions: string[]
  alternatives: string[]
}

export interface Workflow {
  workflow_id: string
  name: string
  description: string
  steps: WorkflowStep[]
  happy_path: string[]
  exception_paths: string[][]
}

export interface BusinessRule {
  rule_id: string
  description: string
  rule_type: string
  applies_to: string[]
  is_explicit: boolean
  confidence: number
}

export interface Ambiguity {
  ambiguity_id: string
  description: string
  severity: AmbiguitySeverity
  affected_requirement: string
  suggested_clarification: string
  blocking: boolean
}

export interface EnrichedContext {
  is_available: boolean
  similar_requirements: Array<{
    requirement_id?: string
    similarity?: number
    test_outcome?: string
  }>
  relevant_domain_knowledge: string[]
  historical_test_patterns: string[]
}

export interface Requirement {
  requirement_id: string
  type: RequirementType
  title: string
  description: string
  acceptance_criteria: string[]
  priority: string
  tags: string[]
  source_reference?: string
}

export interface NormalizedRequirement {
  requirement_id: string
  source: RequirementSource
  metadata: ProcessingMetadata
  status: ProcessingStatus
  requirements: Requirement[]
  entities: Entity[]
  workflows: Workflow[]
  business_rules: BusinessRule[]
  ambiguities: Ambiguity[]
  enriched_context: EnrichedContext
  human_review_required: boolean
  review_reasons: string[]
}

export interface TestStep {
  step_number: number
  action: string
  expected_result: string
}

export interface Assertion {
  assertion_id: string
  description: string
  assertion_type: string
  expected_value: unknown
  operator: string
}

export interface AutomationScaffold {
  framework: string
  language: string
  scaffold_code: string
  file_path_suggestion: string
  imports: string[]
  fixtures_required: string[]
}

export interface TestCase {
  test_id: string
  source_requirement_id: string
  type: string
  priority: string
  title: string
  description: string
  preconditions: string[]
  steps: TestStep[]
  expected_results: string[]
  assertions: Assertion[]
  tags: string[]
  automation_scaffold?: AutomationScaffold
  risk_score: number
  is_duplicate: boolean
  duplicate_of?: string
}

export interface TestSuiteMetadata {
  generated_at: string
  generation_model: string
  total_test_cases: number
  by_type: Record<string, number>
  by_priority: Record<string, number>
  coverage_estimate: number
  human_review_required: boolean
  review_reasons: string[]
}

export interface TestSuite {
  test_suite_id: string
  source_requirement_id: string
  metadata: TestSuiteMetadata
  test_cases: TestCase[]
}

export interface AnalyzeRequest {
  source_type: SourceType
  reference: string
  url?: string
  raw_inputs: Record<string, string>
  job_id?: string
  max_tokens?: number
}

export interface AnalysisProgress {
  current_step: string | null
  completed_steps: string[]
  elapsed_seconds: number
  status: 'running' | 'complete' | 'failed'
  error?: string
  requirement_id?: string
}

export interface RequirementSummary {
  requirement_id: string
  reference: string
  status: ProcessingStatus
  confidence_score: number
  created_at: string
  requirement_count: number
  human_review_required: boolean
  test_suite_id?: string
}

export interface ReviewEvent {
  id: string
  entity_key: string
  entity_type: string
  entity_id: string
  approved: boolean
  reason: string | null
  created_at: string
}
