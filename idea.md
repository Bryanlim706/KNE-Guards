Idea mindmap

                ┌──────────────────────────────┐
                │     Startup Idea Input       │
                │ (product, features, pricing) │
                └──────────────┬───────────────┘
                               │
                               v
        ┌──────────────────────────────────────────┐
        │        PRODUCT INTERPRETER LAYER        │
        │  - extracts features & assumptions      │
        │  - converts into testable hypotheses    │
        └──────────────┬──────────────────────────┘
                               │
                               v
     ┌──────────────────────────────────────────────┐
     │         CONSUMER AGENT GENERATOR            │
     │  (Student / persona simulation builder)     │
     │                                              │
     │  Output:                                     │
     │  - behavior model                            │
     │  - attention span                            │
     │  - motivation triggers                       │
     │  - substitution preferences                 │
     └──────────────┬──────────────────────────────┘
                    │
                    v
   ┌──────────────────────────────────────────────────┐
   │            SIMULATION ENVIRONMENT               │
   │                                                  │
   │  Time Engine:                                   │
   │  - Day 0 (onboarding)                          │
   │  - Day 1–7 (retention)                         │
   │  - Day 30 (habit formation)                   │
   │                                                  │
   │  Context Engine:                                │
   │  - exam week stress                            │
   │  - distraction events                          │
   │  - competing apps (Notion, WhatsApp, etc.)     │
   └──────────────┬──────────────────────────────────┘
                    │
                    v
     ┌──────────────────────────────────────────┐
     │        AGENT DECISION ENGINE             │
     │                                          │
     │ For each consumer agent:                 │
     │  - try product?                          │
     │  - continue using?                      │
     │  - abandon?                             │
     │  - switch to alternative?               │
     │                                          │
     │ Uses:                                   │
     │  - rule-based heuristics                │
     │  - LLM reasoning layer                  │
     └──────────────┬──────────────────────────┘
                    │
                    v
     ┌──────────────────────────────────────────┐
     │        BEHAVIOUR TRACKING LAYER         │
     │                                          │
     │ Logs:                                   │
     │  - adoption rate                        │
     │  - retention curve                      │
     │  - drop-off points                     │
     │  - substitution patterns               │
     └──────────────┬──────────────────────────┘
                    │
                    v
     ┌──────────────────────────────────────────┐
     │         INSIGHT GENERATION AGENT        │
     │                                          │
     │ Outputs:                                │
     │  - why users dropped off               │
     │  - which feature failed                │
     │  - improvement suggestions             │
     │  - viability score                     │
     └──────────────┬──────────────────────────┘
                    │
                    v
     ┌──────────────────────────────────────────┐
     │              DASHBOARD UI               │
     │                                          │
     │  - adoption curve graph                 │
     │  - retention heatmap                   │
     │  - persona breakdown                   │
     │  - failure explanations                │
     └──────────────────────────────────────────┘

Idea Description:
- Product is targetting businesses targetting students as a consumer base
- Product consists of agents which test the product based on their own aggregated behaviour to test whether they would adopt usage into a long term. OR whether the product will be used by rotating users over a long term.