# FP3: Harness (assignment text, copied from Canvas)

In FP2, you designed an agentic system and proposed a study to investigate a specific research question. In this deliverable, you will implement your agentic system as well as the experimental setup needed to conduct that study. By the end of this milestone, you should be able to run your experimental conditions on a set of tasks, record the relevant data, and compute the measures you proposed in FP2, which will become the next deliverable. Please note that you do not need to run your experiments just yet. FP3 is designed to focus on developing a reproducible research instrument.

## Harness Implementation

Your harness will include your agentic application, filesystem, sandbox, and evaluation suite. Your implementation (and your repo) should include the following:

- **A functional agentic system.** Implement the core architecture, tools, and task environment described in the Method section of FP2. The system should run end to end on representative tasks. Document any changes to the proposed design.
- **Experimental conditions.** Implement the conditions/baselines in your FP2 Procedure. You should be able to select a condition through a configuration or run parameter, without manually rewriting your implementation. Clearly identify the manipulated variable(s) and what is held constant across conditions.
- **An experiment runner.** Provide a repeatable way to load tasks from your dataset/benchmark and execute the chosen condition. The runner should identify tasks and trials, support repeated runs when needed, and save results rather than requiring manual collection.
- **Logging and measurement.** Save structured run-level records containing the task ID, condition, trial ID, model/configuration, final output, and the information needed to compute your measures (e.g., agent steps, tool calls, retrievals, errors, timestamps, token usage). Implement code to compute your FP2 metrics from the stored records. Record failures as outcomes rather than silently discarding them. Report token usage/time when available.
- **Evaluation checks.** Verify that your metrics measure what you intend. If you use an LLM judge, document its model, prompt/rubric, and output format, and compare its judgments against human labels on a small sample (aim for at least 20 examples). Report the agreement and any issues you observe.

For benchmark-development projects, the requirements above apply to the benchmark and its evaluation pipeline. In particular:

- Implement the benchmark tasks proposed in FP2, including all task categories, task formats, data sources or generation procedures, and scoring criteria.
- For the pilot, evaluate a representative subset of tasks (at least 20) using baseline models/agents (preferably at least two). Report preliminary performance across task categories and identify potential issues with task quality, difficulty, or scoring.

## FP3 Report sections

- **GitHub repo link** (public).
- **Changes Since FP2.** Briefly summarize changes to research question, architecture, conditions, tasks, or measures. If none, say so. Do not repeat the FP2 proposal.
- **Agentic system and conditions.** Describe what was implemented. Include an updated graph-level architecture diagram showing agent nodes, tools, relevant state/decision points, and where measurements are collected. Explain conditions/baselines, independent variable(s), and components held fixed. Report exact model/version IDs and configuration settings. Make clear how conditions differ.
- **Tasks, metrics, and data collection.** Identify the task dataset/benchmark, including any filtering or sampling. Describe how runs are logged and how FP2 metrics are calculated. Make clear what is recorded at each step and how each metric is derived. If a measure is not yet implemented, state what is missing and why.
- **Pilot Study.** At least 10 representative tasks per condition (one trial per task is sufficient). Same tasks across conditions when possible. Report number of successful/failed runs, the primary FP2 metric(s), average run time and token usage or estimated cost. The pilot exposes implementation/measurement problems; its results are not final findings.
- **Readiness assessment.** Did all conditions run correctly? Were any tasks, tools, or evaluators unreliable? Do traces support the metrics? Floor/ceiling effects? LLM-judge agreement if used. Specific fixes before the full experiment.
- **Plan for FP4.** Number of tasks, conditions, repetitions, expected total runs. Time and API cost estimated from the pilot, with assumptions. What remains before final data collection, division of responsibilities, target dates.

## What to submit

- A zip of the repository with harness files, including saved pilot results (trace records, etc.).
- Repo requirements: README with setup instructions, dependencies, how to run each experimental condition, and how to obtain metric summaries. An example env file if credentials are required (never commit API keys). At least one small sample of saved run records. Python scripts, not notebooks. The repo should look like the repo example from W10b.
- The completed report as a PDF (remove all template prompts).
