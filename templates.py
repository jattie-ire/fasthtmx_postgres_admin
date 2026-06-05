"""Template rendering and Jinja2 setup"""
import jinja2
from pathlib import Path
from datetime import datetime


# Setup Jinja2 environment
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)))


def format_datetime(value):
    """Format datetime without fractional seconds and timezone"""
    if value is None:
        return ""
    if isinstance(value, str):
        # If it's a string like "2026-05-29 11:03:27.463856+0 0:00", extract just date and time
        # Remove timezone and fractional seconds
        parts = value.split('.')[0]  # Remove fractional seconds
        return parts.split('+')[0]  # Remove timezone
    # If it's a datetime object
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


# Add custom Jinja2 filters
jinja_env.filters['format_datetime'] = format_datetime


def render_template(template_name: str, context: dict) -> str:
    """Render a Jinja2 template"""
    try:
        # Add kerberos_domain from config if not already in context
        if 'kerberos_domain' not in context:
            from config import KERBEROS_DOMAIN
            context['kerberos_domain'] = KERBEROS_DOMAIN
        
        template = jinja_env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        print(f"Template error: {e}")
        return f"<h1>Error rendering {template_name}: {e}</h1>"
