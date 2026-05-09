from groq import Groq
import json

class TacticalLLMReporter:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile" # Premium Open Source model

    def generate_report(self, kpi_json):
        if not self.client.api_key:
            return "⚠️ Groq API Key missing."
        
        system_prompt = (
            "Assuming you are a mix of Pep Guardiola and Sir Alex Ferguson, "
            "Create a proper tactical report on the match basis of the metrics and KPIs provided. "
            "Focus on spatial dominance, transition speed, and off-the-ball movement."
        )

        user_content = f"Match KPIs:\n\n{json.dumps(kpi_json, indent=2)}"

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
            return f"Error: {str(e)}"

    def generate_phase_insight(self, phase_data, hull_area, phase_index):
        """
        Deep dive into a SINGLE phase of play.
        Persona: Tactical mastermind explaining game state.
        """
        if not self.client.api_key:
            return "AI Coach unavailable."

        system_prompt = (
            "You are a World-Class Tactical Coach. Explain the current 'Game State' for this specific phase. "
            "Use Markdown formatting for a premium reading experience: "
            "1. Use `###` for headers. "
            "2. Use `> [!TIP]` style callouts for tactical gems. "
            "3. Use bolding for player names and metrics. "
            "Focus on both the Offensive intent and the Defensive reaction. "
            "Round all metrics you mention to 2 decimal places. "
            "Keep it punchy, professional, and instructional."
        )

        context = {
            "phase": phase_index + 1,
            "player": phase_data.get('player'),
            "action": phase_data.get('action'),
            "vaep_impact": round(phase_data.get('vaep', 0), 2),
            "threat_xt": round(phase_data.get('xt', 0), 2),
            "defensive_hull_area": round(float(hull_area), 2)
        }

        user_content = f"Analyze Phase {context['phase']} Game State:\n\n{json.dumps(context, indent=2)}"

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.6,
                max_tokens=600,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"Coach's Insight error: {str(e)}"

if __name__ == "__main__":
    # Test with dummy data
    test_kpis = [
        {"team": "Spain", "def_line_height": 55.2, "peak_run_speed_ms": 9.1, "congestion_5m": 1.8},
        {"team": "England", "def_line_height": 42.1, "peak_run_speed_ms": 8.4, "congestion_5m": 2.3}
    ]
    import os
    api_key = os.getenv("GROQ_API_KEY", "dummy_key")
    reporter = TacticalLLMReporter(api_key)
    print(reporter.generate_report(test_kpis))
