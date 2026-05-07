from groq import Groq
import json

class TacticalLLMReporter:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-specdec"

    def generate_report(self, kpi_json):
        if not self.client.api_key:
            return "⚠️ Groq API Key missing. Please set the GROQ_API_KEY environment variable in Hugging Face Secrets."
        
        system_prompt = (
            "Assuming you are a mix of Pep Guardiola (tactical coach) and Sir Alex Ferguson "
            "(man and opponent management and analysis with 35+ years of professional football experience "
            "at the highest footballing level - Premier League and Champions League) - Create a proper "
            "tactical report on the home team and the away team on the basis of the metrics and KPIs provided. "
            "Focus on spatial dominance, transition speed, and off-the-ball movement. "
            "Make sure the final output does not output 'Guardiola (The Professor)' and 'Ferguson (The Gaffer)' "
            "terms explicitly. These terms are for your internal analysis and report generation only."
        )

        user_content = f"Here are the tactical KPIs for the match in JSON format:\n\n{json.dumps(kpi_json, indent=2)}"

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"Error generating LLM report: {str(e)}"
