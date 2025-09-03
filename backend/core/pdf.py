from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML
from pathlib import Path
import datetime

def render_invoice_pdf(order):
    html = render_to_string("pdf/invoice.html", {"order": order, "today": datetime.date.today()})
    invoices_dir = Path(settings.MEDIA_ROOT) / "invoices"
    invoices_dir.mkdir(parents=True, exist_ok=True)
    filename = f"invoice_order_{order.id}.pdf"
    out_path = invoices_dir / filename
    HTML(string=html, base_url=str(invoices_dir)).write_pdf(str(out_path))
    return str(out_path), filename
