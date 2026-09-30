# Kemet Kaggle GPU Worker

This is a batch GPU worker for Kemet. It is not a second canonical runtime.

Flow:
Kemet canonical runtime -> approved job manifest -> Kaggle Notebook GPU -> real artifact -> SHA-256 evidence -> Kemet verification.

The worker uses Kaggle's free GPU notebook execution and Wan2.1 T2V 1.3B.
It is intentionally batch-oriented because Kaggle Notebooks are sessions, not a permanent HTTPS worker.

Governance:
- human approval remains in Kemet
- execution authority remains false
- no fake capacity or generation evidence
- output is accepted only after artifact hash and job binding verification
- commercial-use licensing must be verified before production admission
