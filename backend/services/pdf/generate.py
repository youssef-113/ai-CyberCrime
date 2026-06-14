"""PDF Generation - WeasyPrint + Jinja2 Templates"""
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import os
from typing import List
from datetime import datetime

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
    """Generate PDF complaint with professional styling"""
    
    # Setup Jinja2
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Select template
    template_name = f"complaint_{language}.html"
    template = env.get_template(template_name)
    
    # Get current date in appropriate format
    if language == "ar":
        generated_date = datetime.now().strftime("%Y/%m/%d")
    else:
        generated_date = datetime.now().strftime("%B %d, %Y")
    
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
        generated_date=generated_date
    )
    
    # Convert to PDF
    html = HTML(string=html_content, base_url=os.path.dirname(__file__))
    
    # Add RTL CSS for Arabic
    if language == "ar":
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "Amiri-Regular.ttf")
        css = CSS(string=f"""
            @font-face {{
                font-family: 'Amiri';
                src: url('file://{font_path}');
            }}
            body {{ direction: rtl; font-family: 'Amiri', 'Traditional Arabic', serif; }}
        """)
        pdf_bytes = html.write_pdf(stylesheets=[css])
    else:
        pdf_bytes = html.write_pdf()
    
    return pdf_bytes