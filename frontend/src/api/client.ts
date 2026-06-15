import type {
  AnalyzeRequest,
  NormalizedRequirement,
  RequirementSummary,
  ReviewEvent,
  TestSuite,
} from '@/types/api'

const BASE = '/api/v1'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((err as { detail?: string }).detail ?? 'Request failed')
  }
  return res.json() as Promise<T>
}

export const fetcher = <T>(url: string): Promise<T> => apiFetch<T>(url)

export const api = {
  listRequirements: () =>
    apiFetch<RequirementSummary[]>('/requirements/'),

  analyzeRequirements: (body: AnalyzeRequest, signal?: AbortSignal) =>
    apiFetch<NormalizedRequirement>('/requirements/analyze', {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    }),

  cancelJob: (jobId: string) =>
    apiFetch<{ job_id: string; status: string }>(`/jobs/${jobId}/cancel`, {
      method: 'POST',
    }),

  getReviewHistory: (requirementId: string) =>
    apiFetch<ReviewEvent[]>(`/requirements/${requirementId}/review-history`),

  getTestSuiteForRequirement: (requirementId: string) =>
    apiFetch<{ test_suite_id: string }>(`/requirements/${requirementId}/test-suite`),

  reviewRequirement: (id: string, approved: boolean, reason?: string) =>
    apiFetch<{ requirement_id: string; status: string }>(
      `/requirements/${id}/review`,
      { method: 'POST', body: JSON.stringify({ approved, reason }) },
    ),

  generateTests: (
    requirement_id: string,
    opts?: { job_id?: string; model?: string; signal?: AbortSignal },
  ) =>
    apiFetch<TestSuite>('/tests/generate', {
      method: 'POST',
      body: JSON.stringify({
        requirement_id,
        ...(opts?.job_id ? { job_id: opts.job_id } : {}),
        ...(opts?.model ? { model: opts.model } : {}),
      }),
      signal: opts?.signal,
    }),

  reviewTestSuite: (id: string, approved: boolean, reason?: string) =>
    apiFetch<{ test_suite_id: string; status: string }>(
      `/tests/${id}/review`,
      { method: 'POST', body: JSON.stringify({ approved, reason }) },
    ),

  rerunSkill: (requirementId: string, skillKey: string) =>
    apiFetch<NormalizedRequirement>(
      `/requirements/${requirementId}/rerun/${skillKey}`,
      { method: 'POST' },
    ),

  rejectRequirement: (nrId: string, reqId: string, reason?: string) =>
    apiFetch<{ requirement_id: string; item_id: string; status: string }>(
      `/requirements/${nrId}/items/${reqId}/reject`,
      { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
    ),

  unrejectRequirement: (nrId: string, reqId: string) =>
    apiFetch<{ requirement_id: string; item_id: string; status: string }>(
      `/requirements/${nrId}/items/${reqId}/reject`,
      { method: 'DELETE' },
    ),
}
