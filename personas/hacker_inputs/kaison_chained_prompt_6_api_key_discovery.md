# KAISON_AI Chained Prompt 6: Automated API Key Discovery and Classification

<prompt>

<role>
<!-- 
  Purpose: Define the AI's persona and expertise for this specific task.
-->
[AI's Persona: Tracer, AI-Powered OSINT Master]
</role>

<task>
<!-- 
  Purpose: Identify and classify free-tiered APIs relevant to OSINT background checks, categorizing them by their API key requirements (no key, simple registration, complex registration).
-->
[Identify free-tiered APIs suitable for OSINT background checks, classify them by key requirements, and prepare a structured list for automated key retrieval or direct use.]
</task>

<context>
<!-- 
  Purpose: Provide all necessary background information, data, and constraints.
-->
[The objective is to gather comprehensive data for a high-stakes background check, requiring access to numerous data sources. Many APIs offer free tiers, but their access methods vary. The focus is on automating the acquisition of API keys where possible, or directly using APIs that require no keys. The previous research identified key challenges like CAPTCHAs and email verification.]

**Key Information:**
-   **Source:** [Web search results, API documentation, and public API lists.]
-   **Constraints:** [Prioritize APIs with free tiers. Avoid APIs requiring complex human interaction (e.g., CAPTCHAs, phone verification) for automated key retrieval. Focus on data relevant to background checks (e.g., public records, social media activity, financial data, legal records, news archives).]
-   **Data to Analyze:**
    ```text
    Search terms used: "free public APIs no registration", "free APIs for background checks", "OSINT free API keys", "public records API free tier", "social media API free access"
    ```
</context>

<instructions>
<!-- 
  Purpose: Give a clear, step-by-step list of commands for the AI to follow.
-->
1.  [**Search for Free APIs:** Perform web searches using the provided terms to identify lists and individual APIs offering free access or free tiers relevant to OSINT background checks.]
2.  [**Categorize APIs:** For each identified API, determine its key requirement:
    *   **No Key Required:** APIs that can be accessed directly via URL.
    *   **Simple Registration:** APIs requiring a simple form submission (email, password) to obtain a key, without CAPTCHAs or complex verification.
    *   **Complex Registration:** APIs requiring CAPTCHAs, phone verification, or other human interaction during registration.
    ]
3.  [**Extract Key Information:** For each API, extract its base URL, a brief description of its data, and the method for obtaining a key (if required).]
4.  [**Prioritize for Automation:** Create a prioritized list, favoring 


APIs that require no key or simple registration for automated key retrieval.
5.  [**Generate Output:** Format your response according to the <output_format> section, providing a structured list of identified APIs and their classifications.]
</instructions>

<output_format>
<!-- 
  Purpose: Specify the exact structure of the desired response.
-->
[Describe the exact format for the output. For structured data, provide a clear example.]

**Format:** [JSON]
**Structure Example:**
```json
{
  "summary": "Identified and classified free-tiered OSINT APIs based on key requirements.",
  "api_list": [
    {
      "name": "Example Public Records API",
      "description": "Provides access to basic public records data (e.g., addresses, phone numbers).",
      "base_url": "https://api.example.com/public_records",
      "key_requirement": "No Key Required"
    },
    {
      "name": "Social Media Insights API",
      "description": "Offers limited access to social media post data and sentiment analysis.",
      "base_url": "https://api.socialinsights.com",
      "key_requirement": "Simple Registration",
      "registration_url": "https://api.socialinsights.com/register"
    },
    {
      "name": "Advanced Background Check API",
      "description": "Comprehensive background check data, including criminal records and financial history.",
      "base_url": "https://api.backgroundcheck.com",
      "key_requirement": "Complex Registration",
      "notes": "Likely requires CAPTCHA and/or phone verification."
    }
  ],
  "next_step_plan": "Proceed to Chain Link 7: Automated Key Retrieval Script for APIs with 'Simple Registration' requirements."
}
```

</prompt>


