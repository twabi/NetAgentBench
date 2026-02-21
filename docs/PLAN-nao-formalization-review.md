# Project Plan: NAO Formalization Flaw Correction (PLAN-nao-flaw-fix.md)

## 1. Context and Objective
The `NAO_formalization.md` document contains structural flaws built upon overfitting to $N=1$ samples in a 25-run benchmark dataset. The 50-run dataset (which doubled the sample size by introducing `gemini-3-flash-preview` on identical tasks) disproves several core theoretical claims, exposing deep flaws related to model variance, absolute algorithmic constraints, and exploration utility.

The objective is to fix these serious flaws by editing the markdown file to reflect the 50-run empirical realities, structurally rewriting mathematically falsified rules.

---

## 2. Implementation Steps (Phase 2)

Based on the brainstorm analysis, we will execute **Option B** to structurally fix the document.

### Step 1: Fix False Constraints on Concurrency (Section 8)
- **Target:** Section 8.2 & 8.3
- **Action:** 
  - Relax $R_{max}(\text{CONCURRENT})$ from $0.5$ to $0.75$.
  - Remove absolute rule `(4) γ = TROUBLESHOOTING ⟹ Π ≠ CONCURRENT` from the Feasibility Filter. 
  - Update text to cite the 50-run empirical evidence: "Concurrent scored 0.691 on BGP Dual-Homing and 0.556 on OSPF Adjacency, indicating isolated subtrees can safely parallelize even in Troubleshooting domains."

### Step 2: Address the Deterministic Fallacy (Section 13)
- **Target:** Section 13 (Claim 1 - Routing Optimality)
- **Action:** 
  - Revise the claim to acknowledge that $\Psi$ must estimate *expected* performance across high-variance LLMs.
  - Remove the deterministic assumption that Single-Agent is the strict baseline, citing its drop to 10% success under the second model.

### Step 3: Fix Premature Meltdown Thresholds (Section 12)
- **Target:** Section 12.3 (Circuit Breaker)
- **Action:** 
  - Change the hardcoded `DestructiveRatio > 0.15` to a dynamic threshold (e.g., `> 0.25` or bounded by task phase).
  - Explicitly state that Troubleshooting requires a higher destructive ratio budget to undo initial broken configuration.

### Step 4: Redefine Exploration Value (Section 9)
- **Target:** Section 9.1 (Risk Amplification / Pattern Affinity)
- **Action:** 
  - Add theoretical justification that Sequential stages benefit heavily from diagnostic separation. (Explaining Sequential's 30.7% exploration rate driving its 40% success).

### Step 5: Update Empirical Grounding (Section 14)
- **Target:** Section 14 (Empirical Grounding)
- **Action:** 
  - Update the table and references to cite the combined 50-run dataset.

---

## 3. Verification Plan
- **Sanity check**: Read through `NAO_formalization.md` post-edit to ensure no mathematical contradictions remain between the Feasibility Filter (Section 8) and the new 50-run text.
- **Formatting**: Ensure mathematical formatting (e.g., $\sigma_D$) and markdown tables are unbroken.
