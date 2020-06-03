import pkg_resources
import qrcode
import os
from PIL import ImageFont, ImageDraw, Image


def gen_qr(url, text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    lines = text.rstrip().split("\n")

    width = 256
    font_size = 16
    font_height = len(lines) * font_size * 2
    height = 256 + font_height
    qr_padding = 6
    text_margin_right = 10

    ttf_path = pkg_resources.resource_filename('mailadm', 'data/opensans-regular.ttf')
    assert os.path.exists(ttf_path), ttf_path

    font = ImageFont.truetype(font=ttf_path, size=font_size)

    image = Image.new("RGB", (width, height), "white")

    draw = ImageDraw.Draw(image)

    draw.multiline_text((text_margin_right, height - font_height), text,
                        font=font, fill="black", align="center")

    qr_final_size = width - (qr_padding * 2)

    image.paste(qr_img.resize((qr_final_size, qr_final_size), resample=Image.NEAREST),
                (qr_padding, qr_padding))

    return image
