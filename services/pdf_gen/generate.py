"""PDF Generation - WeasyPrint + Jinja2 Templates"""
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import os
from typing import List

def generate_complaint_pdf(
    case_id: str,
    crime_type: str,
    evidence_summary: str,
    timeline: List[dict],
    law_articles: List[dict],
    score: int,
    grade: str,
    complainant_name: str,
    language: str = "ar"
) -> bytes:
    """Generate PDF complaint"""
    
    # Setup Jinja2
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Select template
    template_name = f"complaint_{language}.html"
    template = env.get_template(template_name)
    
    # Render HTML
    html_content = template.render(
        case_id=case_id,
        crime_type=crime_type,
        evidence_summary=evidence_summary,
        timeline=timeline,
        law_articles=law_articles,
        score=score,
        grade=grade,
        complainant_name=complainant_name,
        generated_date="2024-01-01"  # Use actual date
    )
    
    # Convert to PDF
    html = HTML(string=html_content)
    
    # Add RTL CSS for Arabic
    if language == "ar":
        css = CSS(string="""
            body { direction: rtl; font-family: 'DejaVu Sans', Arial, sans-serif; }
            .text-left { text-align: right !important; }
        """)
        pdf_bytes = html.write_pdf(stylesheets=[css])
    else:
        pdf_bytes = html.write_pdf()
    
    return pdf_bytes
