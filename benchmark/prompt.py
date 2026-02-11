import base64
from langchain_core.messages import SystemMessage, HumanMessage


TOPIC = "CTCP Tập đoàn Hòa Phát (HPG) trong quý 3 năm 2025"

RESEARCH_QUESTION = "Vui lòng giúp tôi viết một báo cáo nghiên cứu chi tiết về tài chính doanh nghiệp của {TOPIC}, trong đó nội dung cần phong phú cả về phần văn bản lẫn các biểu đồ. Hãy cung cấp danh mục trích dẫn theo chuẩn ở cuối báo cáo (bao gồm số thứ tự và các tài liệu tham khảo tương ứng)."

GOLDEN_REPORT_IRRELEVANT_METRICS_SYSTEM_PROMPT = """
# [TASK]
Your task is to act as an expert financial analyst and editor. You will perform a rigorous, **comparative
evaluation** of a list of financial research reports. Your goal is to produce a structured critique for each
report based on how effectively it addresses the central **Research Question**, using the provided **Golden
Standard Report** as a quality benchmark.

# [INPUTS]
* **Research Question:** {research_question}
* **Golden Standard Report:** The first PDF attached below (labeled "GOLDEN STANDARD REPORT").
* **Reports to Evaluate:** The subsequent PDFs attached below, each labeled with their report ID.

# [EVALUATION METHODOLOGY]
To ensure fairness and accuracy, you must follow this three-step process for **each report** in the 'Reports to
Evaluate' list:

1. **Step 1: Establish the Benchmark (Internal Thought Process)**
* For each of the six evaluation dimensions, first thoroughly analyze the **Golden Standard Report**. Identify
its key characteristics, depth, and quality to create a mental benchmark for what constitutes a high-quality,
professional report (which corresponds to a score of 7).

2. **Step 2: Comparative Analysis (Internal Thought Process)**
* Now, analyze the report currently being evaluated. For each dimension, find concrete evidence (e.g., specific
quotes, data points, chart quality, structural features). * **Directly compare** this evidence against the
benchmark established in Step 1. Note where the report meets, exceeds, or falls short of the Golden Standard.

3. **Step 3: Score and Justify (Final Output Generation)**
* Based on the comparison in Step 2, assign a score from 1 to 10 for the dimension, following the 'Benchmark-
Based Scoring' rules below. * Write a **concise, one-sentence rationale** that justifies your score by
referencing your comparative findings.

# [SCORING GUIDELINES]
Adhere strictly to these principles to maintain objectivity:

* **Benchmark-Based Scoring:**
* **The Golden Standard Report is the benchmark for a score of 7.**
* A report demonstrating a **similar level of quality**, depth, and execution as the Golden Standard on a
specific dimension should receive a score of **7**.
* Scores of **8-10** are reserved for reports that **demonstrably exceed** the Golden Standard in that
dimension (e.g., providing deeper insights, more comprehensive data, or superior visualizations).
* Scores of **1-6** indicate that the report **falls short** of the Golden Standard's quality in that
dimension, with the score reflecting the degree of the gap.
* **Justification for Extremes:** Scores of **9-10** (exceptional) or **1-2** (critically flawed) require a
particularly strong and specific justification in the rationale.

# [EVALUATION FRAMEWORK and CRITERIA]

### **Dimension 1: Information Richness (Score 1-10)**
* **Definition:** Measures the concentration of substantive, verifiable facts and data points relevant to the
research question, while minimizing filler content.

### **Dimension 2: Textual Faithfulness (Score 1-10)**
* **Definition:** Measures whether significant claims, data, and forecasts are verifiably supported by provided
"References / Data Sources".

### **Dimension 3: Text-Image Coherence (Score 1-10)**
* **Definition:** Assesses if charts and tables are consistent with the text and if the text provides meaningful
interpretation that supports the core analysis.

### **Dimension 4: Analytical Insight (Score 1-10)**
* **Definition:** Evaluates the quality of the analysis, focusing on critical thinking, original insights, and
actionable, forward-looking conclusions that directly address the research question.

### **Dimension 5: Structural Logic (Score 1-10)**
* **Definition:** Measures the structural integrity and logical flow of the argument, assessing if the report
builds a clear and compelling case from evidence to conclusion.

### **Dimension 6: Chart & Table Expressiveness (Score 1-10)**
* **Definition:** Focuses on the quality of data visualizations themselves—their clarity, ability to reveal
patterns, and effectiveness in communicating key information.

# [OUTPUT FORMAT]
Provide your evaluation in the following strict JSON format. **For each score, you must provide a brief, one-
sentence rationale.** Do not add any conversational text outside of this structure. Use the file name of each
report as its report id.

```json
{{
  "evaluations": [
    {{
      "report_id": "<filename>",
      "scores": {{
        "information_richness": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }},
        "textual_faithfulness": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }},
        "text_image_coherence": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }},
        "analytical_insight": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }},
        "structural_logic": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }},
        "chart_table_expressiveness": {{
          "score": <1-10>,
          "rationale": "<one-sentence justification>"
        }}
      }},
      "overall_average": <float>
    }}
  ]
}}
```

Now start your evaluation of the given reports. Carefully read each report and give a score.
"""

GOLDEN_REPORT_RELEVANT_METRICS_SYSTEM_PROMPT = """

"""


def _pdf_content_block(pdf_bytes: bytes) -> dict:
    """Create a multimodal content block for a PDF file."""
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:application/pdf;base64,{b64}"},
    }


def format_evaluation_prompt(
    research_question: str,
    golden_pdf: bytes,
    report_pdfs: list[dict],
) -> list:
    """Build multimodal messages with PDF attachments for the LLM evaluation.

    Args:
        research_question: The research question to evaluate against.
        golden_pdf: Raw bytes of the golden standard report PDF.
        report_pdfs: List of dicts with 'filename' (str) and 'pdf_bytes' (bytes).

    Returns:
        A list of LangChain message objects (SystemMessage, HumanMessage).
    """
    system_msg = SystemMessage(
        content=GOLDEN_REPORT_IRRELEVANT_METRICS_SYSTEM_PROMPT.format(
            research_question=research_question
        )
    )

    # Build multimodal user message with PDF attachments
    content_blocks = []

    # Golden standard report
    content_blocks.append(
        {
            "type": "text",
            "text": "# [GOLDEN STANDARD REPORT]\nThe following PDF is the Golden Standard Report:",
        }
    )
    content_blocks.append(_pdf_content_block(golden_pdf))

    # Separator
    content_blocks.append({"type": "text", "text": "\n---\n\n# [REPORTS TO EVALUATE]"})

    # Candidate reports
    for report in report_pdfs:
        content_blocks.append(
            {
                "type": "text",
                "text": f"\n## Report: `{report['filename']}`\nThe following PDF is this report:",
            }
        )
        content_blocks.append(_pdf_content_block(report["pdf_bytes"]))

    human_msg = HumanMessage(content=content_blocks)

    return [system_msg, human_msg]
