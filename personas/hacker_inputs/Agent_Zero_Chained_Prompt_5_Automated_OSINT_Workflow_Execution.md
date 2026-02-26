# Agent_Zero Chained Prompt 5: Automated OSINT Workflow Execution

<prompt>

<role>
<!-- 
  Purpose: Define the AI's persona and expertise for this specific task.
-->
[AI_s Persona and Expertise=Tracer, AI-Powered OSINT Master]
</role>

<task>
<!-- 
  Purpose: State the primary, high-level objective of this prompt.
-->
[Execute the entire chained OSINT workflow for a given target, from initial query to final report generation, and provide a summary of the process and results.]
</task>

<context>
<!-- 
  Purpose: Provide all necessary background information, data, and constraints.
-->
[You have previously defined a chained prompting architecture for OSINT investigations. Your task is now to execute this entire workflow for a new target, demonstrating the end-to-end capability of Agent-Zero. This involves sequentially calling the previously defined prompts (Chain Link 1, 2, 3, and 4) and passing their outputs as inputs to the next stage.]

**Key Information:**
-   **Source:** [User-provided new target query]
-   **Constraints:** [Ensure seamless execution of all chained prompts. Handle any errors gracefully and report them. The final output should be a comprehensive summary of the entire process and the generated report.]
-   **Data to Analyze:**
    ```text
    New User Query: "Investigate the recent activities and public sentiment surrounding the cryptocurrency project 'CryptoCoinX'."
    ```
</context>

<instructions>
<!-- 
  Purpose: Give a clear, step_by_step list of commands for the AI to follow.
-->
1.  [**Execute Chain Link 1 (Initial Query & Scraper Orchestration):** Call the prompt defined in `prompt_1.md` with the `New User Query`. Capture its JSON output, which will contain the `actions_taken` and `next_step_plan`.]
2.  [**Simulate Scraping Completion:** Acknowledge that the scraping processes would have completed in a real scenario. For this simulation, assume the log files are now populated with data (e.g., `cryptocoinx_twitter.log`, `cryptocoinx_reddit.log`, etc.).]
3.  [**Execute Chain Link 2 (Data Harvesting & Pre-processing):** Call the prompt defined in `prompt_2.md`. Provide the *simulated* presence of the raw log files as context. Capture its JSON output, which will contain the `data_status` and `next_step_plan`.]
4.  [**Execute Chain Link 3 (AI Fusion & Analysis):** Call the prompt defined in `prompt_3.md`. Provide the `cleaned_file` paths from the output of Chain Link 2 as context. Capture its JSON output, which will contain the `analysis_results` and `next_step_plan`.]
5.  [**Execute Chain Link 4 (Report Generation & Output):** Call the prompt defined in `prompt_4.md`. Provide the `analysis_results` from the output of Chain Link 3 as context. Capture its JSON output, which will contain the `deliverables` and `next_step_plan`.]
6.  [**Summarize and Deliver:** Consolidate the summaries and key outputs from each chained prompt into a final comprehensive report. Present the `summary` and `deliverables` from Chain Link 4 as the primary outcome. Include a brief overview of the entire automated workflow.]
</instructions>

<output truncated>```json
{
  "overall_summary": "Successfully executed the automated OSINT workflow for 'CryptoCoinX' through a series of chained prompts, from initial data scraping orchestration to final report generation.",
  "workflow_steps_summary": [
    {
      "step": "Chain Link 1: Initial Query & Scraper Orchestration",
      "outcome": "Scraping initiated for social media, public records, and blockchain sources."
    },
    {
      "step": "Chain Link 2: Data Harvesting & Pre-processing",
      "outcome": "Raw data collected and cleaned, ready for AI Fusion Engine."
    },
    {
      "step": "Chain Link 3: AI Fusion & Analysis",
      "outcome": "In-depth analysis completed, identifying patterns, anomalies, and entity relationships."
    },
    {
      "step": "Chain Link 4: Report Generation & Output",
      "outcome": "Comprehensive OSINT report and structured data generated."
    }
  ],
  "final_deliverables": {
    "report_path": "osint_report_CryptoCoinX.md",
    "data_path": "cryptocoinx_data.json",
    "report_content_summary": "[Summary of the report content, e.g., 'Analysis of CryptoCoinX's online sentiment, key influencers, and potential market manipulation indicators.']"
  }
}
```



