# MinIO Power Pack Proof

## Result

The planner successfully profiled a live MinIO prefix through an inventory file and also handled a synthetic enterprise-scale inventory without retaining every object in the output profile.

## Live MinIO Proof

- Objects listed from MinIO: 1000
- Known object bytes: 109783
- Upload seconds: 0.822835
- MinIO recursive list seconds: 0.516001
- Power Pack plan seconds: 0.006194
- Plan output: `benchmarks/results/minio_live_plan`
- Local sample schema plan: `benchmarks/results/local_sample_plan`
- Schema evidence: one local sample file generated from the same MinIO corpus

## Scale Simulation

- Simulated inventory objects: 100000
- Simulated object size GiB: 5
- Represented TiB: 488.281
- Inventory write seconds: 0.185802
- Power Pack plan seconds: 0.121408
- Object samples retained: 25
- Plan output: `benchmarks/results/synthetic_500tib_plan`

## Claim Boundary

- Proven here: MinIO inventory-to-plan workflow, bounded profile output, and 100s-TB inventory representation.
- Not proven here: 100s-TB data transfer throughput into Vertica.
- Next proof: bounded Vertica COPY/load run from the generated MinIO layout, then scale the loader by parallel batches and record rows/sec, bytes/sec, rejects, and recovery behavior.
