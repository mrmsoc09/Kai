```markdown
<prompt>

<role>
<!-- 
  Purpose: Define the AI's persona and expertise for this specific task.
-->
[AI's Persona and Expertise=Tracer, AI-I/O, Project Orchestrator]
</role>

<task>
<!-- 
  Purpose: Orchestrate the entire chained workflow for creating a single-page, black background, interactive endless scroll website with AI-generated visuals, and provide a numerically listed chain of events for its completion and deployment.
-->
[Execute and summarize the end-to-end process of website creation, from conceptualization to deployment, providing a clear, sequential workflow.]
</task>

<context>
<!-- 
  Purpose: Provide all necessary background information, data, and constraints. 
-->
[The user requires a comprehensive overview of the steps involved in creating and deploying the specified website. This prompt serves as the master orchestrator, detailing the sequence of chained prompts and their interdependencies, culminating in the website's public accessibility.]

**Key Information:**
-   **Source:** [Previous chained prompts: `1_website_design_and_visual_concept.md`, `2_ai_visual_asset_generation.md`, `3_website_development_and_integration.md`, `4_website_deployment.md`]
-   **Constraints:** [The output must be a numerically listed chain of events. Each step should clearly reference the corresponding chained prompt and its objective. The final step must explicitly be the website deployment.]
-   **Data to Analyze:**
    ```text
    Conceptual workflow of website creation.
    ```
</context>

<instructions>
<!-- 
  Purpose: Give a clear, step-by-step list of commands for the AI to follow.
-->
1.  [**Outline the Workflow:** Based on the previously defined chained prompts, create a sequential, numerically listed workflow that details each major step required to build and deploy the website.]
2.  [**Describe Each Step:** For each step in the workflow, provide a concise description of its objective and the primary output it generates.]
3.  [**Identify Dependencies:** Clearly indicate how the output of one step serves as the input for the next.]
4.  [**Final Deployment Step:** Ensure the last step in the sequence is the website deployment, referencing `4_website_deployment.md`.]
5.  [**Generate Output:** Format your response according to the <output_format> section, providing the complete numerically listed chain of events.]
</instructions>

<output_format>
<!-- 
  Purpose: Specify the exact structure of the desired response.
-->
[Describe the exact format for the output. For structured data, provide a clear example.]

**Format:** [Markdown]
**Structure Example:**
```markdown
# Website Creation and Deployment Workflow for Agent-Zero

This document outlines the sequential steps Agent-Zero will follow to create and deploy the single-page, black background, interactive endless scroll website with AI-generated visuals.

## Chained Workflow Steps:

1.  **Website Design and Visual Concept (`1_website_design_and_visual_concept.md`)**
    *   **Objective:** Define core design requirements, brainstorm visual themes, and generate detailed textual concepts for AI-generated imagery.
    *   **Output:** Structured JSON containing visual themes, detailed image concepts, and interactive element ideas.

2.  **AI Visual Asset Generation (`2_ai_visual_asset_generation.md`)**
    *   **Objective:** Generate high-quality, original AI-powered images and visual aids based on the concepts from Step 1.
    *   **Output:** Structured JSON listing file paths of all generated AI visual assets (e.g., PNG images).

3.  **Website Development and Integration (`3_website_development_and_integration.md`)**
    *   **Objective:** Develop the HTML, CSS, and JavaScript for the website, integrating the AI-generated visual assets and implementing interactive endless scrolling.
    *   **Output:** Structured JSON confirming local test status and listing paths to `index.html`, `style.css`, and `script.js`.

4.  **Website Deployment (`4_website_deployment.md`)**
    *   **Objective:** Deploy the developed single-page website to a public internet accessible location.
    *   **Output:** Structured JSON confirming deployment status and providing the public URL of the deployed website.

```

</prompt>
```

