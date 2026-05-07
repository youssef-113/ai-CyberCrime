import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
 
 
def generate_pdf(title: str, body: str, output_path: str = "complaint.pdf"):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("complaint_ar.html")
    html_content = template.render(title=title, body=body)
 
    HTML(string=html_content, base_url=BASE_DIR).write_pdf(output_path)
    print(f"PDF saved to: {output_path}")
 
 
if __name__ == "__main__":
    generate_pdf(
        title="شكوى قانونية",
        body="بناءً على أحكام القانون المصري، يتقدم المشتكي بهذه الشكوى الرسمية.",
        output_path="complaint.pdf"
    )