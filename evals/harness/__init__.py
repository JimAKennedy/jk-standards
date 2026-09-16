"""LLM-judged skill evaluation harness (jk-standards, docs/plans/skill-evals).

Lives outside the shipped package on purpose: the check registry, the
boundaries invariants, and the base install know nothing about it. The
`eval` validation token (`make eval`) is the only consumer.
"""
