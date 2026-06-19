---
created: '2026-05-07T16:33:08+00:00'
evidence:
- stage-02/problem_tree.md
id: problem_decompose-rc-20260507-162814-43d8e9
run_id: rc-20260507-162814-43d8e9
stage: 02-problem_decompose
tags:
- problem_decompose
- stage-02
- run-rc-20260
title: 'Stage 02: Problem Decompose'
---

# Stage 02: Problem Decompose

## Source

Derived from the user-provided Stage 01 research brief and the referenced AQ draft path: `/Users/jackiewang/Desktop/AQ/icml26_ai4science_draft.tex`. No external verification or file inspection is assumed here.

## Sub-questions

1. **What Hamiltonian path families are physically valid and QLSP-correct?**  
   Define admissible \(H(s;\theta)\) classes that satisfy boundary conditions, Hermiticity, sparsity/locality, normalization, smoothness, and final-state encoding of the QLSP solution. This is the foundation: without a valid path space, learned improvements may be physically meaningless.

2. **For a fixed path, what is the best traversal policy \(s(t)\)?**  
   Compare analytic local-adiabatic schedules, constrained RL schedules, and differentiable optimal-control schedules under monotonicity, smoothness, runtime, and control-amplitude constraints. Key question: do learned schedules actually track spectral-gap structure?

3. **Which path-geometry features improve finite-size adiabatic QLSP performance?**  
   Study whether learned paths increase minimum gaps, reduce integrated adiabatic error proxies, avoid sharp gap bottlenecks, or improve robustness to perturbations in \(A\) and \(b\). Distinguish genuine path gains from schedule-only gains.

4. **How should the bilevel outer-inner optimization be coupled?**  
   Decide whether the outer path search should optimize against an exact inner optimum, a learned approximate controller, a differentiable surrogate, or alternating updates. This determines whether the framework is scientifically interpretable or just an expensive black-box optimizer.

5. **When is constrained RL preferable to differentiable optimal control?**  
   Identify regimes where RL handles non-smooth constraints, discrete path choices, noisy objectives, or adaptive policies better than gradient methods, and regimes where differentiable control is cheaper, more stable, and easier to interpret.

6. **Do ancilla-assisted path families expand the feasible design space in useful ways?**  
   Test whether adding ancilla degrees of freedom can create smoother or larger-gap interpolations while preserving QLSP correctness after projection/postselection. This should be treated as an extension, not the core claim.

7. **What benchmark families expose the right failure modes?**  
   Construct AQ-QLSP PathBench around controlled spectra, condition numbers, sparsity, gap bottlenecks, and right-hand-side alignment. Include at least three matrix families and three \(\kappa\) regimes so results are not tied to one synthetic artifact.

8. **Where do known \(\kappa\)-scaling limits dominate?**  
   Explicitly test cases where learned paths and schedules cannot improve beyond known asymptotic barriers. The paper should frame gains as finite-size constant-factor, robustness, and practical-control improvements, not asymptotic breakthroughs.

## Priority Ranking

1. **P0: Valid path parameterization**  
   Needed before any learning experiment is meaningful.

2. **P0: Fixed-path schedule comparison**  
   Establishes the inner-layer baseline: analytic schedule vs constrained RL vs differentiable optimal control.

3. **P0: Bilevel objective and evaluation protocol**  
   Defines how outer path search receives feedback from inner traversal performance.

4. **P1: Learned path geometry analysis**  
   Tests whether outer search improves gaps, error proxies, or robustness beyond schedule tuning.

5. **P1: RL vs differentiable-control regime map**  
   Important for positioning the paper against generic ML-control work.

6. **P1: \(\kappa\)-barrier and negative-result analysis**  
   Essential for credibility and avoiding overclaiming.

7. **P2: Ancilla-assisted extensions**  
   Valuable if core results are strong, but should not block the main paper.

8. **P2: Optional real sparse matrices**  
   Useful for realism only if preprocessing and Hermitian embedding remain lightweight.

## Risks

- **Invalid learned Hamiltonians:** unconstrained optimization may violate Hermiticity, boundary correctness, sparsity, or QLSP encoding.
- **Schedule gains may dominate:** improvements could come entirely from adaptive traversal, not path discovery.
- **Minimum gap may be misleading:** integrated adiabatic error and transition matrix elements may matter more than \(\Delta_{\min}\) alone.
- **RL instability:** constrained RL may be sample-inefficient or noisy compared with differentiable control on small exact-simulation tasks.
- **Overclaiming asymptotics:** learned finite-size improvements must not be framed as beating known optimal \(\kappa\)-dependence.
- **Benchmark artifact risk:** synthetic families may reward path parameterizations that do not generalize.
- **Compute creep:** bilevel optimization with exact diagonalization and Schrödinger evolution can become expensive unless dimensions and path classes are tightly controlled.