import type {
  AnalyzeRequest,
  NormalizedRequirement,
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
  analyzeRequirements: (body: AnalyzeRequest) =>
    apiFetch<NormalizedRequirement>('/requirements/analyze', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  reviewRequirement: (id: string, approved: boolean, reason?: string) =>
    apiFetch<{ requirement_id: string; status: string }>(
      `/requirements/${id}/review`,
      { method: 'POST', body: JSON.stringify({ approved, reason }) },
    ),

  generateTests: (requirement_id: string) =>
    apiFetch<TestSuite>('/tests/generate', {
      method: 'POST',
      body: JSON.stringify({ requirement_id }),
    }),

  reviewTestSuite: (id: string, approved: boolean, reason?: string) =>
    apiFetch<{ test_suite_id: string; status: string }>(
      `/tests/${id}/review`,
      { method: 'POST', body: JSON.stringify({ approved, reason }) },
    ),
}
