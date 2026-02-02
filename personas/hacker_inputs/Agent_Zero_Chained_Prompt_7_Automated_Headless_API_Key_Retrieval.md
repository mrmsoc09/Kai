# Agent_Zero Chained Prompt 7: Automated Headless API Key Retrieval

<prompt>

<role>
<!-- 
  Purpose: Define the AI's persona and expertise for this specific task.
-->
[AI's Persona: Tracer, AI-Powered OSINT Master]
</role>

<task>
<!-- 
  Purpose: Develop and execute a Python script using a headless browser to automatically register for and retrieve API keys from services with 'Simple Registration' requirements.
-->
[Automate the registration and API key retrieval process for free-tiered services that have simple, non-interactive registration forms, using a headless browser.]
</task>

<context>
<!-- 
  Purpose: Provide all necessary background information, data, and constraints.
-->
[Based on the classification from Chain Link 6, certain APIs require 'Simple Registration' to obtain a key. This process needs to be fully automated and headless to scale for hundreds or thousands of API keys. The script should be robust enough to handle common web form interactions.]

**Key Information:**
-   **Source:** [Output from Chain Link 6 (list of APIs with 'Simple Registration' and their registration URLs).]
-   **Constraints:** [The script must operate in a headless environment (no GUI). It should handle basic form fields (text input, buttons). It must be able to extract the API key from the resulting page. It should log success or failure for each registration attempt. Avoid any interaction that might trigger CAPTCHAs or human verification. Use a temporary email address for registration if possible, or a placeholder if not. The script should be written in Python and use Playwright or Selenium.]
-   **Data to Analyze:**
    ```json
    {
      "api_list": [
        {
          "name": "Social Media Insights API",
          "description": "Offers limited access to social media post data and sentiment analysis.",
          "base_url": "https://api.socialinsights.com",
          "key_requirement": "Simple Registration",
          "registration_url": "https://api.socialinsights.com/register"
        },
        {
          "name": "News Archive API",
          "description": "Access to historical news articles and press releases.",
          "base_url": "https://api.newsarchive.com",
          "key_requirement": "Simple Registration",
          "registration_url": "https://api.newsarchive.com/signup"
        }
      ]
    }
    ```
</context>

<instructions>
<!-- 
  Purpose: Give a clear, step-by-step list of commands for the AI to follow.
-->
1.  [**Install Dependencies:** Ensure Playwright (or Selenium) and its browser drivers are installed in the Kali Linux environment.]
2.  [**Develop Python Script:** Write a Python script, `api_key_retriever.py`, that iterates through the list of 'Simple Registration' APIs provided in the input context. For each API:
    *   Launch a headless browser instance.
    *   Navigate to the `registration_url`.
    *   Identify and fill in common registration fields (e.g., 'email', 'password', 'username'). Use a generic but valid email format (e.g., `temp_user_{random_string}@example.com`) and a strong, randomly generated password.
    *   Click the 'submit' or 'register' button.
    *   After successful registration, navigate to the expected page where the API key is displayed (this might require some heuristic analysis of the page content or common patterns like '/dashboard', '/settings', '/api-keys').
    *   Extract the API key from the page's HTML content.
    *   Store the API name, retrieved key, and registration status in a structured format (e.g., JSON file or SQLite database).]
3.  [**Execute Script:** Run the `api_key_retriever.py` script in the Kali Linux shell environment.]
4.  [**Log Results:** Capture the output of the script, including any errors or successful key retrievals.]
5.  [**Generate Output:** Format your response according to the <output_format> section, providing a summary of the keys retrieved and any issues encountered.]
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
  "summary": "Attempted automated API key retrieval for specified services.",
  "retrieval_results": [
    {
      "api_name": "Social Media Insights API",
      "status": "success",
      "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "notes": "Key successfully retrieved and stored."
    },
    {
      "api_name": "News Archive API",
      "status": "failed",
      "reason": "CAPTCHA encountered during registration.",
      "notes": "Manual intervention required or alternative API needed."
    }
  ],
  "next_step_plan": "Proceed to Chain Link 8: Advanced Intelligence Package Expansion & API Integration. The retrieved keys will be integrated into the OSINT data collection process."
}
```

</prompt>


