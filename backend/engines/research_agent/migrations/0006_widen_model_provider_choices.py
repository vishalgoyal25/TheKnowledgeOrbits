"""
0006_widen_model_provider_choices
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Widen AgentExecutionLog.model_provider choices to cover the post-Cerebras LLM pool.

Context: FEATURES_LLM_FIX.md — Cerebras began returning 402 Payment Required on
2026-08-19, so research_agent now pools groq + mistral + openrouter.

SAFETY NOTES
  • ADDITIVE ONLY. Migrations 0001–0005 are untouched.
  • Django `choices` is validation metadata, NOT a database constraint: this
    AlterField emits no destructive DDL. On PostgreSQL it is effectively a
    no-op at the table level and cannot lock or rewrite the table.
  • "cerebras" and "gemini" are deliberately RETAINED in the choice list.
    Existing rows still carry "cerebras"; removing the choice would render
    historical records invalid in admin and forms.
  • No data migration. No column added, dropped or renamed. Fully reversible.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("research_agent", "0005_channel_core"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agentexecutionlog",
            name="model_provider",
            field=models.CharField(
                choices=[
                    ("groq", "Groq"),
                    ("mistral", "Mistral"),
                    ("openrouter", "OpenRouter"),
                    ("cerebras", "Cerebras"),
                    ("gemini", "Gemini"),
                ],
                max_length=32,
            ),
        ),
    ]
