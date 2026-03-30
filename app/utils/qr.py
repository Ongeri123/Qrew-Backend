import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from app.config import settings


def generate_qr_code(venue_slug: str, format: str = "png") -> str:
    """
    Generate a QR code for a venue
    Returns base64 encoded image string

    format: "png" or "svg"
    """
    # The URL players scan
    url = f"{settings.app_url}/play/{venue_slug}"

    if format == "svg":
        return _generate_svg(url)
    return _generate_png(url)


def _generate_png(url: str) -> str:
    """Generate PNG QR code as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{encoded}"


def _generate_svg(url: str) -> str:
    """Generate SVG QR code as string — scales perfectly for print"""
    factory = qrcode.image.svg.SvgImage
    qr = qrcode.make(url, image_factory=factory)

    buffer = BytesIO()
    qr.save(buffer)
    buffer.seek(0)

    return buffer.getvalue().decode("utf-8")


def get_venue_url(venue_slug: str) -> str:
    """Return the plain URL for a venue"""
    return f"{settings.app_url}/play/{venue_slug}"